from ddddocr import DdddOcr


class MyDdddOcr:
    @classmethod
    def extract_verify_code_from_img(cls, captcha_img_path):
        with open(captcha_img_path, 'rb') as f:
            img_bytes = f.read()
        return cls.extract_verify_code_from_bytes(img_bytes)

    @classmethod
    def extract_verify_code_from_bytes(cls, captcha_img_bytes):
        return DdddOcr(show_ad=False).classification(captcha_img_bytes)



if __name__ == '__main__':
    captcha_path = r"C:\Users\lovel\Desktop\Snipaste_2026-01-27_22-24-49.png"
    val = MyDdddOcr.extract_verify_code_from_img(captcha_path)
    print(val)
