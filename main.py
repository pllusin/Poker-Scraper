from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from datetime import datetime
import os
import logging
from time import sleep

# تنظیمات لاگ‌گیری
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# بارگذاری تنظیمات از فایل .env
load_dotenv()

# متغیرهای کانفیگ
THREADS = int(os.getenv('THREADS'))
START_TIME = datetime.strptime(os.getenv('START_TIME'), "%H:%M:%S").time()
ACCOUNTS_FILE = os.getenv('ACCOUNTS_FILE')

# تنظیمات ضد‌شناسایی
HEADLESS_MODE = os.getenv('HEADLESS_MODE', 'true').lower() == 'true'
DISABLE_BLINK_FEATURES = os.getenv('DISABLE_BLINK_FEATURES', 'true').lower() == 'true'
EXCLUDE_AUTOMATION = os.getenv('EXCLUDE_AUTOMATION', 'true').lower() == 'true'


def create_driver():
    try:
        options = Options()
        
        if HEADLESS_MODE:
            options.add_argument('--headless')
        
        if DISABLE_BLINK_FEATURES:
            options.add_argument("--disable-blink-features=AutomationControlled")
        
        # تنظیمات جدید برای رفع مشکل لود نشدن jQuery و iframe
        options.set_preference("network.http.connection-timeout", 60000)
        options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", True)
        options.set_preference("media.navigator.permission.disabled", True)
        options.set_preference("dom.webnotifications.enabled", False)
        options.set_preference("dom.push.enabled", False)
        
        # تنظیمات امنیتی و دسترسی
        options.set_preference("security.fileuri.strict_origin_policy", False)
        options.set_preference("security.mixed_content.block_active_content", False)
        options.set_preference("security.mixed_content.block_display_content", False)
        options.set_preference("privacy.trackingprotection.enabled", False)
        options.set_preference("network.http.referer.XOriginPolicy", 0)
        options.set_preference("network.http.referer.spoofSource", True)
        
        # تنظیمات DNS و پروکسی
        options.set_preference("network.proxy.type", 0)
        options.set_preference("network.dns.disablePrefetch", False)
        options.set_preference("network.prefetch-next", True)
        
        # تنظیمات JavaScript
        options.set_preference("javascript.enabled", True)
        options.set_preference("dom.disable_beforeunload", True)
        
        logging.info("Creating Firefox driver...")
        service = Service('/usr/bin/geckodriver')
        driver = webdriver.Firefox(service=service, options=options)
        
        # تنظیم timeout ها
        driver.set_page_load_timeout(60)  # افزایش timeout
        driver.set_script_timeout(60)
        
        logging.info("Firefox driver created successfully")
        return driver
        
    except Exception as e:
        logging.error(f"Error creating driver: {e}")
        raise


# تابع لاگین و ثبت‌نام
def login_and_register(account):
    try:
        username, password = account
        logging.info(f"Starting process for account: {username}")
        
        driver = create_driver()
        logging.info("Driver created, navigating to website...")
        
        driver.get("https://www.pokerklas628.com/")
        logging.info("Website loaded successfully")
        
        # اضافه کردن کد بستن تبلیغ با سلکتورهای مختلف
        try:
            # اول تبلیغ رو می‌بندیم
            WebDriverWait(driver,2).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#announcementPopup button.close"))
            ).click()
            
            # کمی صبر می‌کنیم تا انیمیشن بستن تبلیغ تمام شود
            sleep(1)
            
            
            logging.info("Advertisement and backdrop removed successfully")
        except Exception as e:
            logging.warning(f"Could not close advertisement: {e}")
            try:
                driver.execute_script("""
                    document.querySelector('#announcementPopup').style.display = 'none';
                    document.querySelector('.modal-backdrop').remove();
                """)
                logging.info("Advertisement closed using JavaScript")
            except Exception as js_error:
                logging.error(f"Failed to close advertisement with JavaScript: {js_error}")
        
        # کمی صبر می‌کنیم تا مطمئن شویم همه چیز پاک شده
        sleep(1)
        
        # منتظر باز شدن دکمه لاگین
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/header/section[2]/nav/button[1]'))
        ).click()
        
        # سوئیچ به فرم لاگین
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '/html/body/div[7]/div/div'))
        )

        # وارد کردن اطلاعات کاربری
        driver.find_element(By.XPATH, '//*[@id="loginStepStarter"]/label[1]/input').send_keys(username)
        driver.find_element(By.XPATH, '//*[@id="loginStepStarter"]/label[2]/input').send_keys(password)
        driver.find_element(By.XPATH, '//*[@id="loginStepStarter"]/button').click()

        # تایید لاگین
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="memberSecureWordVerify"]'))
        ).click()

        # به جای کار با iframe، مستقیماً URL رو باز می‌کنیم
        try:
            logging.info("Finding poker URL...")
            # صبر برای لود شدن iframe و گرفتن URL آن
            iframe = WebDriverWait(driver, 20).until(
                lambda x: x.find_element(By.CSS_SELECTOR, "iframe[src*='pokerplaza']")
            )
            poker_url = iframe.get_attribute('src')
            logging.info(f"Found poker URL: {poker_url}")
            
            # باز کردن مستقیم URL
            driver.get(poker_url)
            logging.info("Navigated to poker URL directly")
            
            # صبر برای لود شدن صفحه
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="root"]'))
            )
            logging.info("Found root element")
            
            # صبر برای ناپدید شدن لودینگ
            WebDriverWait(driver, 30).until(
                EC.invisibility_of_element_located((By.CLASS_NAME, "lobby-loader"))
            )
            logging.info("Loading completed")
            
            # کمی تاخیر اضافی
            sleep(2)
            
            # کلیک روی لینک تورنمنت‌ها
            tournament_link = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="root"]/div/div[1]/div/section[1]/header/div[1]/ul/li[2]/a'))
            )
            tournament_link.click()
            logging.info("Clicked on tournament link")
            
        except Exception as e:
            logging.error(f"Error in poker interaction: {e}")
            raise
            
    except Exception as e:
        logging.error(f"Error processing account {username}: {str(e)}")
        raise
    finally:
        try:
            if driver:
                driver.quit()
                logging.info(f"Driver closed for account: {username}")
        except Exception as e:
            logging.error(f"Error closing driver: {str(e)}")

# خواندن فایل اکانت‌ها
def read_accounts(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    return [tuple(line.strip().split(',')) for line in lines]

# زمان‌بندی اجرای تسک‌ها
def schedule_jobs(accounts, threads, start_time):
    # Timing disabled for development
    # while datetime.now().time() < start_time:
    #     sleep(1)

    with ThreadPoolExecutor(max_workers=threads) as executor:
        executor.map(login_and_register, accounts)

# اجرای اصلی
if __name__ == "__main__":
    accounts = read_accounts(ACCOUNTS_FILE)
    logging.info(f"Loaded {len(accounts)} accounts.")
    
    # Remove this line as it's incorrect:
    # login_and_register(accounts)
    
    # Use ThreadPoolExecutor to process accounts
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        executor.map(login_and_register, accounts)

