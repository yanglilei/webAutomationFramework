import base64
import os
import numpy as np
import cv2


def base64_to_image(base64_str, save_path):
    """
    将Base64编码的图片字符串转换为图片并保存到本地

    参数:
        base64_str (str): Base64编码的图片字符串（可能包含前缀，如data:image/jpeg;base64,）
        save_path (str): 图片保存路径（需包含文件名和扩展名，如"output.png"）

    返回:
        bool: 成功返回True，失败返回False
    """
    try:
        # 处理Base64字符串中的前缀（如data:image/jpeg;base64,）
        if 'base64,' in base64_str:
            # 提取纯Base64编码部分（去掉前缀）
            base64_data = base64_str.split('base64,')[-1]
        else:
            base64_data = base64_str

        # Base64解码（转换为二进制数据）
        image_data = base64.b64decode(base64_data)

        # 创建保存目录（如果不存在）
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)

        # 写入文件保存为图片
        with open(save_path, 'wb') as f:
            f.write(image_data)

        print(f"图片已成功保存至: {save_path}")
        return True

    except base64.binascii.Error:
        print("错误：Base64编码格式无效，请检查输入字符串")
        return False
    except Exception as e:
        print(f"保存失败：{str(e)}")
        return False


def cv2_imread(file_path, flags=cv2.IMREAD_COLOR):
    """
    支持中文路径的 cv2.imread 替代方法

    参数:
        file_path (str): 图片路径（可含中文）
        flags (int): 读取模式，同 cv2.imread
            - cv2.IMREAD_COLOR (1): 彩色图（默认）
            - cv2.IMREAD_GRAYSCALE (0): 灰度图
            - cv2.IMREAD_UNCHANGED (-1): 包含 alpha 通道的原图
    返回:
        numpy.ndarray: 读取的图像，失败返回 None
    """
    try:
        # 以二进制方式读取文件
        with open(file_path, 'rb') as f:
            img_data = f.read()
        # 将二进制数据转换为 numpy 数组并解码
        img = cv2.imdecode(np.frombuffer(img_data, dtype=np.uint8), flags)
        return img
    except Exception as e:
        print(f"读取图片失败：{e}")
        return None

# 配套：支持中文路径的保存函数（可选）
def cv2_imwrite(file_path, img):
    """支持中文路径的 cv2.imwrite 替代方法"""
    try:
        # 编码图像数据
        ext = file_path.split('.')[-1].lower()
        if ext in ['jpg', 'jpeg']:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
            _, img_data = cv2.imencode('.jpg', img, encode_param)
        elif ext == 'png':
            encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 0]
            _, img_data = cv2.imencode('.png', img, encode_param)
        else:
            # 默认用原图格式编码
            _, img_data = cv2.imencode('.' + ext, img)
        # 写入文件
        with open(file_path, 'wb') as f:
            img_data.tofile(f)
        return True
    except Exception as e:
        print(f"保存图片失败：{e}")
        return False


def auto_crop_image(input_path, output_path=None, background_threshold=30):
    """
    自动化裁剪图片，去除周围单一颜色背景（默认黑色背景）

    参数:
        input_path (str): 输入图片路径（支持jpg、png等格式）
        output_path (str): 输出图片路径（默认在输入路径后加"_cropped"）
        background_threshold (int): 背景阈值（0-255），低于此值视为背景（默认30，适合黑色背景）

    返回:
        bool: 裁剪成功返回True，失败返回False
    """
    try:
        # 1. 读取图片（支持透明通道）
        img = cv2_imread(input_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"错误：无法读取图片 {input_path}")
            return False

        # 2. 处理透明通道（若存在）：透明区域视为背景
        if img.shape[-1] == 4:  # 有Alpha通道
            b, g, r, a = cv2.split(img)
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            # 透明区域（a=0）设为背景（0）
            gray[a == 0] = 0
        else:  # 无透明通道，直接转灰度图
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 3. 阈值分割：区分背景和有效内容（高于阈值的为有效内容）
        _, thresh = cv2.threshold(gray, background_threshold, 255, cv2.THRESH_BINARY)

        # 4. 查找有效内容的轮廓，确定最小边界框
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            print("警告：未检测到有效内容，可能全是背景")
            return False

        # 合并所有轮廓的边界，找到整体最小/最大坐标
        min_x, min_y = gray.shape[1], gray.shape[0]
        max_x, max_y = 0, 0
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)

        # 5. 裁剪图片（确保坐标在有效范围内）
        min_x = max(0, min_x)
        min_y = max(0, min_y)
        max_x = min(gray.shape[1], max_x)
        max_y = min(gray.shape[0], max_y)
        cropped_img = img[min_y:max_y, min_x:max_x]

        # 6. 保存裁剪后的图片
        if output_path is None:
            # 默认输出路径：输入路径文件名后加"_cropped"
            dir_name, file_name = os.path.split(input_path)
            name, ext = os.path.splitext(file_name)
            output_path = os.path.join(dir_name, f"{name}_cropped{ext}")

        cv2_imwrite(output_path, cropped_img)
        print(f"图片已自动裁剪并保存至：{output_path}")
        return True

    except Exception as e:
        print(f"裁剪失败：{str(e)}")
        return False

def crop_image(input_path, output_path, x1, y1, x2=None, y2=None):
    """
    裁剪图片指定区域（支持x2、y2默认使用图片右下角坐标）

    参数:
        input_path (str): 输入图片路径
        output_path (str): 输出裁剪后图片路径
        x1 (int): 裁剪区域左上角x坐标（从0开始）
        y1 (int): 裁剪区域左上角y坐标（从0开始）
        x2 (int, optional): 裁剪区域右下角x坐标，默认使用图片宽度
        y2 (int, optional): 裁剪区域右下角y坐标，默认使用图片高度

    说明:
        - 坐标以图片左上角为原点(0,0)，向右为x轴正方向，向下为y轴正方向
        - 若不填x2/y2，默认裁剪到图片右下角（x2=图片宽度，y2=图片高度）
        - 需保证 x1 < x2 且 y1 < y2，坐标不能超出原图尺寸范围
    """
    # 读取图片
    img = cv2_imread(input_path)
    if img is None:
        raise ValueError(f"无法读取图片，请检查路径：{input_path}")

    # 获取图片尺寸（高度、宽度）
    height, width = img.shape[:2]  # height对应y轴范围，width对应x轴范围

    # 处理默认值：x2默认取图片宽度，y2默认取图片高度
    if x2 is None:
        x2 = width
    if y2 is None:
        y2 = height

    # 校验坐标合法性
    if x1 < 0 or y1 < 0:
        raise ValueError("坐标不能为负数")
    if x2 > width or y2 > height:
        raise ValueError(f"坐标超出图片范围（图片宽：{width}，高：{height}）")
    if x1 >= x2 or y1 >= y2:
        raise ValueError("请保证 x1 < x2 且 y1 < y2")

    # 裁剪图片（OpenCV切片格式：[y1:y2, x1:x2]）
    cropped_img = img[y1:y2, x1:x2]

    # 保存裁剪结果
    success = cv2_imwrite(output_path, cropped_img)
    if not success:
        raise IOError(f"保存图片失败，请检查输出路径：{output_path}")

    print(f"裁剪成功！已保存至：{output_path}（裁剪区域：({x1},{y1}) 至 ({x2},{y2})）")


# 使用示例
if __name__ == "__main__":
    try:
        # 示例1：只指定左上角坐标，默认裁剪到图片右下角
        crop_image(
            input_path=r"D:\PycharmProjects\learnRobotV2\dist\安溪继续教育考试助手V1.0.0\tmp\350524196708056516_slider_bg_img.png",
            output_path=r"D:\PycharmProjects\learnRobotV2\dist\安溪继续教育考试助手V1.0.0\tmp\350524196708056516_slider_bg_img2.png",
            x1=56   ,  # 左上角x
            y1=0  # 左上角y（x2和y2不填，默认用图片右下角）
        )

        # # 示例2：指定完整坐标（与原功能一致）
        # crop_image(
        #     input_path="input.jpg",
        #     output_path="cropped_full.jpg",
        #     x1=50,
        #     y1=50,
        #     x2=300,
        #     y2=200
        # )
    except Exception as e:
        print(f"出错：{e}")