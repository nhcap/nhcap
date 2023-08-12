## nhcap
python undetected_chromedriver 的自动解决hcaptcha
### 支持的类型
|类型         | 支持情况                        | 模型训练                    |  缺点                                         |优点                                     |demo|
|   -------   |             -------             |           -------           |                    -------                    |                 -------                 |-------|
|九宫格点选    | 需要对应的yolov5模型(支持中英文)  | 训练容易                     |hcaptcha更新较快一个模型可能只能支持几小时        |训练需要配数据集少(80张图片)，绝大多数可训练 |[demo](https://streamable.com/e/bb1wa3) |
|图片选择位置  | 需要对应的yolov5模型(仅支持中文)  | 训练需要相对较多的数据集       |需要的训练数据较多，hcaptcha更新未测试，预估(7天) |坚持时间长                                |[demo](https://streamable.com/e/1zj1z7) |
|选择图片对应动物/物品  | 未支持                  | 未支持                        |需要的训练数据很多，模型只能允许一个大类一个模型  |未测试                                    |未支持|

#### 使用
下载[nhcap](https://github.com/nhcap/nhcap/tree/main/nhcap)内的文件
```
pip install -r requriements.txt
```
在你的python中导入nhcap.py
```python
from nhcap import run1
```
打开网页调用
```python
run1(driver)
```

例:
```python
from nhcap import run1
import undetected_chromedriver as uc

if __name__ == '__main__':
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    driver.get("https://2captcha.com/demo/hcaptcha?difficulty=easy")
    run1(driver)
    input('1')
    driver.quit()
```

#### 代码重构:
将来可能会重构，现在代码很乱并且没有注释

#### 训练自己的模型教程：
应该会出

