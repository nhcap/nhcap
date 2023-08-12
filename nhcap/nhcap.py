import torch
from PIL import Image
from loguru import logger
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
import time
import re
import requests
import random
import io
import os
import json
import base64
log1 = False #详细日志(应该也没啥)
timeout = 10  #如果在多长时间没有找到hcaptcha直接返回
model_dir = 'models'   #模型文件夹

xpath_list = [
    '/html/body/div/div[1]/div/div/div[2]/div[1]',
    '/html/body/div/div[1]/div/div/div[2]/div[2]',
    '/html/body/div/div[1]/div/div/div[2]/div[3]',
    '/html/body/div/div[1]/div/div/div[2]/div[4]',
    '/html/body/div/div[1]/div/div/div[2]/div[5]',
    '/html/body/div/div[1]/div/div/div[2]/div[6]',
    '/html/body/div/div[1]/div/div/div[2]/div[7]',
    '/html/body/div/div[1]/div/div/div[2]/div[8]',
    '/html/body/div/div[1]/div/div/div[2]/div[9]'
]

new2_xpath_list = [
    '/html/body/div/div[1]/div/div/div[2]/div/div[2]/div[1]',
    '/html/body/div/div[1]/div/div/div[2]/div/div[2]/div[2]',
    '/html/body/div/div[1]/div/div/div[2]/div/div[2]/div[3]',
]

def find_id(new1, info):
    return new1.get(info, None)

def find_coordinates(label, detection_results):
    for result in detection_results:
        if result[0] == label:
            return result[2]
    return None

def get_center(bbox):
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

def calculate_click_coordinates(img, bbox):
    image_width, image_height = img.size
    bbox_pixel = (
        bbox[0] * image_width,   # x1
        bbox[1] * image_height,  # y1
        bbox[2] * image_width,   # x2
        bbox[3] * image_height   # y2
    )
    center_pixel = get_center(bbox_pixel)
    canvas_original_width = 1000
    canvas_original_height = 1072
    canvas_display_width = 500
    canvas_display_height = 536
    center_canvas_original = (
        center_pixel[0] * canvas_original_width / image_width,
        center_pixel[1] * canvas_original_height / image_height
    )
    center_canvas_display = (
        center_canvas_original[0] * canvas_display_width / canvas_original_width,
        center_canvas_original[1] * canvas_display_height / canvas_original_height
    )
    return center_canvas_display

def load_models():
    model_dict = {}
    for model_file in os.listdir(model_dir):
        if model_file.endswith('.pt'):
            json_file = model_file.replace('.pt', '.json')
            json_path = os.path.join(model_dir, json_file)
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    model_info = json.load(f)
                model_dict[model_info['cnname']] = {'model_file': model_file, 'cl': model_info['cl'], 'modeid': model_info['modeid']}
                model_dict[model_info['enname']] = {'model_file': model_file, 'cl': model_info['cl'], 'modeid': model_info['modeid']}
    logger.info(f'已加载 {len(model_dict)//2} 个模型')
    return model_dict

def exit(driver, xpath2):
    try:
        iframe = driver.find_element(By.XPATH, xpath2)
        iframe_location = iframe.location
        iframe_size = iframe.size
        body = driver.find_element(By.TAG_NAME, 'body')
        body_size = body.size
        while True:
            rand_x = random.randint(0, body_size['width'])
            rand_y = random.randint(0, body_size['height'])
            if not (iframe_location['x'] <= rand_x <= iframe_location['x'] + iframe_size['width'] and
                    iframe_location['y'] <= rand_y <= iframe_location['y'] + iframe_size['height']):
                break
        actions = ActionChains(driver)
        actions.move_to_element_with_offset(body, rand_x, rand_y)
        actions.click()
        actions.perform()
    except:
        logger.error('退出错误')

def merge_image_with_blank(img, img_width=100, img_height=100, blank_width=500, blank_height=500):
    blank_img = Image.new('RGB', (blank_width, blank_height), (255, 255, 255))
    img_merge = Image.new('RGB', (img_width + blank_width, img_height), (255, 255, 255))
    img = img.resize((img_width, img_height))
    img_merge.paste(img, (0, 0))
    img_merge.paste(blank_img, (img_width, 0))
    return img_merge

def modelstart(path):
    logger.info('开始加载模型，接下来的输出不是报错!')
    try:
        model = torch.hub.load('ultralytics/yolov5', 'custom', path=path)
    except Exception as e:
        logger.error(f'加载模型出错: {e}')
        sys.exit()
    logger.info('模型加载完毕')
    return model

def detection1(model, img, cl=0.5, id=0):
    results = model(img)
    confidences = results.xyxyn[0][:, 4].cpu().numpy()
    labels = results.xyxyn[0][:, -1].cpu().numpy()
    has_fruit = any((label == id) and (conf > cl) for label, conf in zip(labels, confidences))
    if log1 == True:
        logger.info(has_fruit)
    return(has_fruit)

def detection2(model, img, cl=0.5):
    results = model(img)
    detections = results.xyxyn[0].cpu().numpy()
    detection_results = []
    for detection in detections:
        x1, y1, x2, y2, confidence, label = detection
        if confidence > cl:
            detection_results.append((label, confidence, (x1, y1, x2, y2)))
    if log1 == True:
        logger.info(detection_results)
    return detection_results

def clickspj(driver, model, modlename, xpath, cl=0.5, id=0):
    if model == None:
        model = modelstart(f'modle/{modlename}')
    xpath1 = f'{xpath}/div[2]/div'
    # 定位到div元素
    wait = WebDriverWait(driver, 10)
    div_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath1)))
    style = div_element.get_attribute('style')
    url = re.search(r'url\("(.+?)"\)', style).group(1)
    try:
        response = requests.get(url)
    except:
        logger.error('下载图片失败')
        return
    img_data = response.content
    img_io = io.BytesIO(img_data)
    img1 = Image.open(img_io)
    img = merge_image_with_blank(img1)
    if detection1(model, img, cl=cl , id=id):
        div_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        div_element.click()

def new2click1(driver, modle, xpath, max_detection_id, cl=0.5):
    xpath1 = f'{xpath}/div[2]/div/div'
    element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath1)))
    style_attribute = element.get_attribute('style')
    image_url = style_attribute.split('url("')[1].split('")')[0]
    try:
        response = requests.get(image_url)
    except:
        logger.error('下载图片失败')
        return
    img_data = response.content
    img_io = io.BytesIO(img_data)
    img1 = Image.open(img_io)
    image = merge_image_with_blank(img1)
    j = detection2(modle, image, cl=cl)
    if max_detection_id in [detection[0] for detection in j]:
        driver.find_element(By.XPATH, xpath).click
        return True

def new2click2(driver, cnname, xpath):
    xpath1 = f'{xpath}/div[1]/div/div'
    element = driver.find_element_by_xpath(xpath1)
    text = element.text
    if cnname == text:
        driver.find_element(By.XPATH, xpath).click
        return True

def detection(driver):
    start_time = time.time()
    while True:
        try:
            driver.find_element(By.XPATH, "//iframe[@title='Widget containing checkbox for hCaptcha security challenge']")
            logger.info('找到hcaptcha en')
            return("//iframe[@title='Widget containing checkbox for hCaptcha security challenge']", "//iframe[@title='Main content of the hCaptcha challenge']", "en")
        except:
            pass
        try:
            driver.find_element(By.XPATH, "//iframe[@title='包含 hCaptcha 安全挑战复选框的小部件']")
            logger.info('找到hcaptcha cn')
            return("//iframe[@title='包含 hCaptcha 安全挑战复选框的小部件']", "//iframe[@title='hCaptcha挑战的主要内容']", "cn")
        except:
            pass
        if time.time() - start_time > timeout:
            logger.error('未找到hcaptcha')
            return False

def display(driver, xpath1):
    wait = WebDriverWait(driver, 10)
    frame = wait.until(EC.presence_of_element_located((By.XPATH, xpath1)))        
    driver.switch_to.frame(frame)
    element = driver.find_element(By.XPATH, '/html/body/div/div[1]/div[1]/div/div[@id="anchor-state"]/div[2]')
    display = element.value_of_css_property('display')
    driver.switch_to.default_content()
    if display == 'block':
        return True
    elif display == 'none':
        return False

def chikekre(driver, xpath1, xpath2):    #点击验证码
    if load(driver, xpath2, time=0.1) == True:
        logger.info('验证码已经点击')
        return True
    if display(driver, xpath1) == True:
        logger.info('已经正在加载')
        return True
    wait = WebDriverWait(driver, 10)
    try:
        frame = wait.until(EC.presence_of_element_located((By.XPATH, xpath1)))        
        driver.switch_to.frame(frame)
        #checkbox = driver.find_element(By.XPATH, '//*[@id="checkbox"]')
        checkbox = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="checkbox"]')))
        checkbox.click()
        driver.switch_to.default_content()
        return True
    except Exception as e:
        driver.switch_to.default_content()
        logger.error('点击验证码错误')
        logger.error(e)
        return False

def solve(driver, xpath1):
    wait = WebDriverWait(driver, 5)
    frame = wait.until(EC.presence_of_element_located((By.XPATH, xpath1)))
    driver.switch_to.frame(frame)
    #checkbox = driver.find_element(By.XPATH, '//*[@id="checkbox"]')
    checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="checkbox"]')))
    aria_checked_value = checkbox.get_attribute('aria-checked')
    driver.switch_to.default_content()
    if aria_checked_value == 'false':
        logger.info('未解决hcapthca')
        return False
    elif aria_checked_value == 'true':
        logger.info('解决成功')
        return True

def load(driver, xpath2, time=20):
    wait = WebDriverWait(driver, time)
    frame_challenge = wait.until(EC.presence_of_element_located((By.XPATH, xpath2)))
    driver.switch_to.frame(frame_challenge)
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[1]/div')))
        driver.switch_to.default_content()
        return True
    except:
        driver.switch_to.default_content()
        logger.info('未加载验证码')
        return False



#执行刷取指定
def beath(driver, xpath2, language, model_dict):
    wait = WebDriverWait(driver, 10)
    y = load(driver, xpath2)
    if y == False:
        return False
    frame_challenge = wait.until(EC.presence_of_element_located((By.XPATH, xpath2)))
    driver.switch_to.frame(frame_challenge)
    
    start_time = time.time()
    while True:
        try:
            driver.find_element(By.XPATH, "/html/body/div/div[1]/div/div/div[1]/div[1]/div[2]")
            logger.info('九宫格')
            break
        except:
            pass
        try:
            element = driver.find_element(By.XPATH, "/html/body/div/div[1]/div/div/div[1]/h2")
            text = element.text
            logger.info('新验证码')
            if '请点击' in text:
                match = re.search(r'请点击(.+)', text)
                m = match.group(1)
                logger.info(f'新验证码1,{m},测试中(鹦鹉识别效果不佳)')
                lo1 = hcpnew1(driver, m)
                if lo1 == False:
                    logger.info('解决失败，刷新')
                    wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[2]/div[4]'))).click()
                    time.sleep(2)
                driver.switch_to.default_content()
                return
            elif '下图中显示的是什么动物' in text:
                logger.info('新验证码2，不可执行，刷新')
                wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[2]/div[4]'))).click()
                driver.switch_to.default_content()
                time.sleep(2)
                return
            elif '在下图中你能看见什么物体' in text:
                logger.info('新验证码2，不可执行，刷新')
                wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[2]/div[4]'))).click()
                driver.switch_to.default_content()
                time.sleep(2)
                return
            else:
                logger.info(f'不能解决{text},刷新')
                wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[2]/div[4]'))).click()
                driver.switch_to.default_content()
                time.sleep(2)
                return
        except Exception as e:
            input('1')
            logger.error(e)
            pass
        if time.time() - start_time > 20:
            logger.error('未加载完毕')
            return

    try:
        content_element = wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[1]/div/div/div[1]/div[1]/div[1]/h2/span')))
    except:
        logger.info('不可执行或未加载,刷新')
        click_element = wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[2]/div[4]')))
        click_element.click()
        driver.switch_to.default_content()
        return
    
    content = content_element.get_attribute('innerHTML')
    if language == 'cn':
        pattern = re.compile(r'含(.*?)的')
        match = pattern.search(content)
        m = match.group(1)
    elif language == 'en':
        m= content.split()[-1]
    logger.info(f'关键词{m}')
    if m in model_dict:
        model_info = model_dict[m]
        modlename = model_info['model_file']
        cl = model_info['cl']
        modeid = model_info['modeid']
        logger.info(f'{m} 可以执行')
        hcpty(driver, m, modlename, cl=cl, modelj=modeid)
        driver.switch_to.default_content()
        return
    else:
        logger.info('不可执行,刷新')
        try:
            click_element = wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[2]/div[4]')))
            click_element.click()
        except:
            logger.error('点击刷新失败')
        driver.switch_to.default_content()
        time.sleep(2)
        return
    

def run1(driver):
    model_dict = load_models()
    time.sleep(1)
    find1 = detection(driver)
    if find1 == False:
        return False
    else:
        xpath1, xpath2, language = find1
    #chink1 = chikekre(driver, xpath1)
    if chikekre(driver, xpath1, xpath2) == False:
        return False
    while True:
        beath(driver, xpath2, language, model_dict)
        if solve(driver, xpath1) == True:
            return True
        if load(driver, xpath2, time=0.1) == False:
            if chikekre(driver, xpath1, xpath2) == False:
                return False


#模型区域

def hcpty(driver, info, modlename, cl=0.5, modelj=0):
    wait = WebDriverWait(driver, 10)
    if modelj == 0:
        model = modelstart(f'{model_dir}/{modlename}')
    else:
        model = None
    while True:
        random.shuffle(xpath_list)
        for xpath in xpath_list:
            clickspj(driver, model, modlename, xpath, cl=cl)
        final_div_xpath = '/html/body/div/div[3]/div[3]'
        final_div_element = wait.until(EC.presence_of_element_located((By.XPATH, final_div_xpath)))
        final_div_element.click()
        try:
            logger.info('等待4秒检查')
            time.sleep(4)
            waitdz = WebDriverWait(driver, 1)
            content_element = waitdz.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[1]/div/div/div[1]/div[1]/div[1]/h2/span')))
            content = content_element.get_attribute('innerHTML')
            pattern = re.compile(r'含(.*?)的')
            match = pattern.search(content)
            if info != match.group(1):
                logger.error('解决失败，退出')
                break
            logger.info(f'未解决{match.group(1)}')
        except:
            logger.info('可能已经解决')
            break



def hcpnew1(driver, info):
    wait = WebDriverWait(driver, 10)
    modle = modelstart(f'nmodels/new1_2.pt')
    with open('nmodels/new1_2.json', 'r', encoding='utf-8') as f:
        model_info = json.load(f)
    new1 = {}
    for key, value in model_info["data"].items():
        new1[key] = value
    logger.info(new1)
    id = find_id(new1, info)
    if id == None:
        logger.info('没有对应的id')
        return False
    while True:
        canvas = driver.find_element(By.XPATH, '/html/body/div/div[1]/div/div/canvas')
        canvas_base64 = driver.execute_script("return arguments[0].toDataURL('image/png').substring(21);", canvas)
        canvas_png = base64.b64decode(canvas_base64)
        image = Image.open(io.BytesIO(canvas_png))
        j = detection2(modle, image, cl=0.5)
        coordinates = find_coordinates(id, j)
        if coordinates == None:
            logger.info('没有对应')
            return False
        canvas = driver.find_element(By.XPATH, '/html/body/div/div[1]/div/div/canvas')
        click_coordinates = calculate_click_coordinates(image, coordinates)
        logger.info(f'位置{click_coordinates}')
        offset = (258, 276)
        click_coordinates = (int(click_coordinates[0]), int(click_coordinates[1]))
        adjusted_coordinates = (click_coordinates[0] - offset[0], click_coordinates[1] - offset[1])
        actions = ActionChains(driver)
        actions.move_to_element_with_offset(canvas, adjusted_coordinates[0], adjusted_coordinates[1])
        actions.pause(0.5)
        actions.click()
        actions.pause(0.5)
        actions.perform()
        logger.info('点击完毕')
        final_div_xpath = '/html/body/div/div[3]/div[3]'
        final_div_element = wait.until(EC.presence_of_element_located((By.XPATH, final_div_xpath)))
        final_div_element.click()
        try:
            logger.info('等待4秒检查')
            time.sleep(4)
            element = driver.find_element(By.XPATH, "/html/body/div/div[1]/div/div/div[1]/h2")
            text = element.text
            match = re.search(r'请点击(.+)', text)
            m = match.group(1)
            if info != m:
                logger.error('解决失败，退出')
                return False
            logger.info(f'未解决{m}')
        except:
            logger.info('可能已经解决')
            return True
