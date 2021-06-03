# -*- coding:utf-8 -*-
import sys 
from PIL import Image

from Crypto.Cipher import AES  
from base64 import b64decode, b64encode


import argparse




BLOCK_SIZE = AES.block_size
# 不足BLOCK_SIZE的补位(s可能是含中文，而中文字符utf-8编码占3个位置,gbk是2，所以需要以len(s.encode())，而不是len(s)计算补码)
pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * (BLOCK_SIZE - len(s) % BLOCK_SIZE).to_bytes(1,'little')
# 去除补位
unpad = lambda s: s[:-ord(s[len(s) - 1:])]


class AESCipher:
    def __init__(self, secretkey):
        self.key = secretkey  # 密钥
        self.iv = secretkey[0:16]  # 偏移量

    def encrypt(self, text):
        """
        加密 ：先补位，再AES加密，后base64编码
        :param text: 需加密的明文
        :return:
        """
        # text = pad(text) 包pycrypto的写法，加密函数可以接受str也可以接受bytess
        text = pad(text) # 包pycryptodome 的加密函数不接受str
        cipher = AES.new(key=self.key, mode=AES.MODE_CBC, IV=self.iv)
        encrypted_text = cipher.encrypt(text)
        # 进行64位的编码,返回得到加密后的bytes，decode成字符串
        return encrypted_text#b64encode(encrypted_text).decode('utf-8')

    def decrypt(self, encrypted_text):
        """
        解密 ：偏移量为key[0:16]；先base64解，再AES解密，后取消补位
        :param encrypted_text : 已经加密的密文
        :return:
        """
        #encrypted_text = b64decode(encrypted_text)
        cipher = AES.new(key=self.key, mode=AES.MODE_CBC, IV=self.iv)
        decrypted_text = cipher.decrypt(encrypted_text)
        return unpad(decrypted_text)


def make_even_image(image):
    """取得一个 PIL 图像并且更改所有值为偶数，使最低有效位为 0
    """
    # image.getdata 方法返回的是一个可迭代对象，其中包含图片中所有像素点的数据
    # 每个像素点表示一个颜色，每种颜色有红绿蓝三种颜色按比例构成
    # R Red 红色；G Green 绿色；B Blue 蓝色；A Alpha 透明度
    # 更改所有像素点中四个数值为偶数（魔法般的移位）
    # 这里使用位运算符 >> 和 << 来实现数据处理
    # 奇数减一变偶数，偶数不变，这样处理后，所有数值的最低位变为零
    # pixels 为更改后的像素点数据列表
    pixels = [(r >> 1 << 1, g >> 1 << 1, b >> 1 << 1, a >> 1 << 1) 
            for r, g, b, a in image.getdata()]  
    # 调用 Image 的 new 方法创建一个相同大小的图片副本
    # 参数为模式（字符串）和规格（二元元组）
    # 这里使用 image 的属性值即可
    even_image = Image.new(image.mode, image.size)  
    # 把处理之后的像素点数据写入副本图片
    even_image.putdata(pixels)  
    return even_image


def encode_data_in_image(image, data):
    """将字符串编码到图片中
    """
    # 获得最低有效位为 0 的图片副本
    even_image = make_even_image(image)  
    # 匿名函数用于将十进制数值转换成 8 位二进制数值的字符串
    int_to_binary_str = lambda i: '0' * (8 - len(bin(i)[2:])) + bin(i)[2:]
    # 将需要隐藏的字符串转换成二进制字符串
    # 每个字符转换成二进制之后，对应一个或多个字节码
    # 每个字节码为一个十进制数值，将其转换为 8 为二进制字符串后相加
    binary = ''.join(map(int_to_binary_str, data))
    # 每个像素点的 RGBA 数据的最低位都已经空出来，分别可以存储一个二进制数据
    # 所以图片可以存储的最大二进制数据的位数是像素点数量的 4 倍
    # 如果需要隐藏的字符串转换成二进制字符串之后的长度超过这个数，抛出异常
    if len(binary) > len(even_image.getdata()) * 4:  
        raise Exception("Error: Can't encode more than " + 
                len(even_image.getdata()) * 4 + " bits in this image. ")
    # 二进制字符串 binary 的长度一定是 8 的倍数
    # 将二进制字符串信息编码进像素点中
    # 当二进制字符串的长度大于像素点索引乘以 4 时
    # 这些像素点用于存储数据
    # 否则，像素点内 RGBT 数值不变
    encoded_pixels = [(r+int(binary[index*4+0]),
                       g+int(binary[index*4+1]),
                       b+int(binary[index*4+2]),
                       t+int(binary[index*4+3])) 
            if index * 4 < len(binary) else (r,g,b,t) 
            for index, (r, g, b, t) in enumerate(even_image.getdata())] 
    # 创建新图片以存放编码后的像素
    encoded_image = Image.new(even_image.mode, even_image.size)  
    # 把处理之后的像素点数据写入新图片
    encoded_image.putdata(encoded_pixels)  
    # 返回图片对象
    return encoded_image


def binary_to_string(binary):
    '''将二进制字符串转换为 UTF-8 字符串
    '''
    # 参数 binary 为二进制字符串，且长度为 8 的倍数
    # index 是 binary 的索引，初始值为 0
    index = 0
    # 创建空列表，以用于添加解析得到的人类能够看懂的 UTF-8 字符
    hide_bytes = b''
    while index < len(binary):
        bits8 = binary[index:index+8]
        int8 = int(bits8,2)
        hide_bytes+=int8.to_bytes(1,'little')
        index += 8

    return hide_bytes


def decode_data_from_image(image):
    '''解码图片中的隐藏数据
    '''
    # 从图片的像素点数据中获得存储数据的二进制字符串
    binary = ''.join([bin(r)[-1] + bin(g)[-1] + bin(b)[-1] + bin(a)[-1]
            for r, g, b, a in image.getdata()]).encode()
    # 出现连续 32 个 0 的字符串片段的索引判定为有效数据截止处
    many_zero_index = binary.find(b'0' * 32)
    # 有效数据字符串的长度一定是 8 的倍数
    # 以此判定准确的断点索引，获得有效数据的二进制字符串
    end_index = (many_zero_index + 8 - many_zero_index % 8 
            if many_zero_index % 8 != 0 else many_zero_index)
    data = binary_to_string(binary[:end_index])
    return data

def encrpt_zip(zip_file,mypass):
    myzip_fd = open(zip_file,'rb')
    contents = myzip_fd.read() #bytes 160
    #print(repr(contents))
    myenc = AESCipher(mypass)
    myzip_fd.close()
    return myenc.encrypt(contents)

def decrpt_zip(zip_file,mypass,contents):
    myzip_fd = open(zip_file,'wb')
    myenc = AESCipher(mypass)
    decrpt_data=myenc.decrypt(contents)
    myzip_fd.write(decrpt_data)
    myzip_fd.close()
    return

def main():
    parser = argparse.ArgumentParser(description="change")
    parser.add_argument('-z','--zip',help='zip')
    parser.add_argument('-p','--png',help='png')
    parser.add_argument('-m', '--mode', default='encode', help='encode or decode.')
    parser.add_argument('-o','--output',default='encodeImage.png',help='name of output picture.')
    args = parser.parse_args()
    myzip = args.zip
    image_file = args.png
    mode = args.mode
    new_image_file=args.output
    if mode == 'encode':
        contents_to_hide=encrpt_zip(myzip,b'WfgOMWDZeqB7vhxU')
        # 调用 Image 的 open 方法获取原图片对象
        image = Image.open(image_file)
        # 调用此函数生成包含字符串数据的新图片对象
        new_image = encode_data_in_image(image, contents_to_hide)
        # 将新图片对象保存到新文件里
        new_image.save(new_image_file)
    if mode == 'decode':
        image = Image.open(image_file)
        # 调用此函数获取隐藏在新图片对象中的字符串并打印
        decode_data = decode_data_from_image(image)
        decrpt_zip(myzip,b'WfgOMWDZeqB7vhxU',decode_data)




if __name__ == '__main__':
    main()
