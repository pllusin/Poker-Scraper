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
import pandas as pd
import argparse
import coloredlogs
import verboselogs
from termcolor import colored
import logging.handlers

# تنظیمات لاگ‌گیری
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# بارگذاری تنظیمات از فایل .env
load_dotenv()

# متغیرهای کانفیگ
THREADS = int(os.getenv('THREADS'))

# تنظیمات ضد‌شناسایی
HEADLESS_MODE = os.getenv('HEADLESS_MODE', 'true').lower() == 'true'
DISABLE_BLINK_FEATURES = os.getenv('DISABLE_BLINK_FEATURES', 'true').lower() == 'true'
EXCLUDE_AUTOMATION = os.getenv('EXCLUDE_AUTOMATION', 'true').lower() == 'true'

# تغییر در بخش پارس کردن آرگومان‌ها
parser = argparse.ArgumentParser(description='Poker Tournament Registration Bot')

# تغییر آرگومان اکسل به لیستی از فایل‌ها
parser.add_argument('excel_files', type=str, nargs='+', help='Path to Excel file(s) containing accounts')

# حذف گروه متقابلاً انحصاری و اضافه کردن آرگومان‌های مستقل
parser.add_argument('--event', action='store_true', help='Run tournament registration')
parser.add_argument('--balance', action='store_true', help='Check balances')

args = parser.parse_args()

# اگر هیچ عملیاتی انتخاب نشده، خطا نمایش داده شود
if not (args.event or args.balance):
    parser.error("At least one of --event or --balance must be specified")

# تنظیم متغیرهای گلوبال
CHECK_BALANCE = args.balance
RUN_EVENT = args.event
ACCOUNTS_FILE = args.excel_files

def setup_main_logger():
    logger = verboselogs.VerboseLogger('Main')
    
    # تنظیم فرمت جدید برای لاگ‌ها
    fmt = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'
    
    coloredlogs.install(
        level='DEBUG',
        logger=logger,
        fmt=fmt,
        datefmt=datefmt,
        level_styles={
            'debug': {'color': 'white'},
            'info': {'color': 'white', 'bold': True, 'prefix': 'ℹ️ '},
            'success': {'color': 'green', 'bold': True, 'prefix': '✅ '},
            'warning': {'color': 'yellow', 'bold': True, 'prefix': '⚠️ '},
            'error': {'color': 'red', 'bold': True, 'prefix': '😢 '},
            'critical': {'background': 'red', 'bold': True, 'prefix': '🚨 '},
        }
    )
    
    return logger

# در ابتدای برنامه
main_logger = setup_main_logger()

def setup_logging():
    # غیرفعال کردن لاگ‌های اضافی سلنیوم
    selenium_logger = logging.getLogger('selenium')
    selenium_logger.setLevel(logging.ERROR)
    urllib3_logger = logging.getLogger('urllib3')
    urllib3_logger.setLevel(logging.ERROR)

def setup_logger(username):
    # رنگ‌های ثابت برای هر کاربر بر اساس نام کاربری
    colors = {
        'red': ['bold'],
        'green': ['bold'],
        'yellow': ['bold'],
        'blue': ['bold'],
        'magenta': ['bold'],
        'cyan': ['bold'],
        'white': ['bold']
    }
    
    # انتخاب رنگ ثابت برای هر کاربر
    color_name = list(colors.keys())[hash(username) % len(colors)]
    
    logger = verboselogs.VerboseLogger(username)
    
    # تنظیم فرمت جدید برای لاگ‌ها
    fmt = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'
    
    # تنظیم لاگ فایل
    os.makedirs('logs', exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        f'logs/{username}.log',
        maxBytes=1024*1024,
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(fmt, datefmt))
    
    # تنظیم لاگ کنسول با رنگ ثابت برای هر کاربر
    coloredlogs.install(
        level='DEBUG',
        logger=logger,
        fmt=fmt,
        datefmt=datefmt,
        level_styles={
            'debug': {'color': color_name},
            'info': {'color': color_name, 'bold': True, 'prefix': 'ℹ️ '},
            'success': {'color': 'green', 'bold': True, 'prefix': '✅ '},
            'warning': {'color': 'yellow', 'bold': True, 'prefix': '⚠️ '},
            'error': {'color': 'red', 'bold': True, 'prefix': '😢 '},
            'critical': {'background': 'red', 'bold': True, 'prefix': '🚨 '},
        }
    )
    
    logger.addHandler(file_handler)
    return logger

def create_driver(logger):
    try:
        options = Options()
        
        # تنظیم مسیر دقیق باینری فایرفاکس
        firefox_binary = '/usr/bin/firefox'  # مسیر پیش‌فرض در اوبونتو
        if not os.path.exists(firefox_binary):
            firefox_binary = '/snap/bin/firefox'  # مسیر جایگزین برای نصب snap
        
        options.binary_location = firefox_binary
        
        if HEADLESS_MODE:
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-extensions')
            
            # تنظیمات اضافی برای حالت هدلس
            options.set_preference('browser.cache.disk.enable', False)
            options.set_preference('browser.cache.memory.enable', False)
            options.set_preference('browser.cache.offline.enable', False)
            options.set_preference('network.http.use-cache', False)
        
        if DISABLE_BLINK_FEATURES:
            options.add_argument("--disable-blink-features=AutomationControlled")
        
        logger.info("Creating Firefox driver...")

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

        
        # تلاش برای یافن geckodriver
        try:
            # اول تلاش می‌کنیم از مسیر نسبی
            service = Service('./geckodriver')
            driver = webdriver.Firefox(service=service, options=options)
        except Exception as e:
            logger.warning(f"Could not create driver with relative path: {e}")
            try:
                # سپس تلاش می‌کنیم از مسیر کامل
                service = Service('/usr/local/bin/geckodriver')
                driver = webdriver.Firefox(service=service, options=options)
            except Exception as e:
                logger.warning(f"Could not create driver with absolute path: {e}")
                # در نهایت تلاش می‌کنیم از PATH سیستم
                service = Service('geckodriver')
                driver = webdriver.Firefox(service=service, options=options)
        
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(60)
        
        logger.info("Firefox driver created successfully")
        return driver
        
    except Exception as e:
        logger.error(f"Error creating driver: {e}")
        raise

def retry_on_failure(max_attempts=3, delay=5):
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            last_exception = None
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    last_exception = e
                    
                    # گرفتن logger از پارامترها یا ساخت یک logger جدید
                    logger = kwargs.get('logger', main_logger)
                    
                    if attempts < max_attempts:
                        logger.warning(f"Attempt {attempts}/{max_attempts} failed: {str(e)}")
                        sleep(delay)
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}. Last error: {str(e)}")
            
            return None
        return wrapper
    return decorator

@retry_on_failure(max_attempts=3, delay=5)
def login_and_register(account):
    username = account['username']
    logger = setup_logger(username)
    driver = None

    try:
        if not CHECK_BALANCE and account['registered']:
            logger.info(f"Account {username} is already registered for tournament: {account['registered_tournament']}")
            return
            
        logger.info(f"Starting process for account: {username}")
        if account['start_time']:
            logger.info(f"Scheduled start time: {account['start_time'].strftime('%H:%M:%S')}")
        
        if CHECK_BALANCE:
            logger.info("Running in BALANCE CHECK mode")
            
        driver = create_driver(logger)
        
        # ... بقیه کد ...
        driver.get("https://www.pokerklas628.com/")
        logger.info("Website loaded successfully")
        # بستن تبلیغ
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#announcementPopup button.close"))
            ).click()
            logger.info("Advertisement closed")
            sleep(1)
        except Exception as e:
            logger.warning("Trying to close advertisement with JavaScript...")
            try:
                driver.execute_script("""
                    var popup = document.querySelector('#announcementPopup');
                    if(popup) popup.style.display = 'none';
                    var backdrop = document.querySelector('.modal-backdrop');
                    if(backdrop) backdrop.remove();
                """)
            except Exception:
                logger.warning("Could not close advertisement")

        # لاگین
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/header/section[2]/nav/button[1]'))
        ).click()
        
        # وارد کردن اطلاعات کاربری
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="loginStepStarter"]/label[1]/input'))
        ).send_keys(username)
        driver.find_element(By.XPATH, '//*[@id="loginStepStarter"]/label[2]/input').send_keys(account['password'])
        driver.find_element(By.XPATH, '//*[@id="loginStepStarter"]/button').click()

        # تایید لاگین
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="memberSecureWordVerify"]'))
        ).click()
        
        logger.info("Login successful")
        sleep(2)

        # اگر در حالت چک بالانس هستم
        if CHECK_BALANCE:
            check_balance(driver, username, logger, account)
            return
            
        # در غیر این صورت ادامه روند عادی برنامه...
        # کد مربوط به ثبت‌نام در تورنمنت

        # رفتن به صفحه پوکر
        logging.info("Navigating to poker page...")
        driver.get("https://www.pokerklas628.com/tablegames/poker")
        
        # صبر برای لود شدن jQuery
        WebDriverWait(driver, 20).until(
            lambda driver: driver.execute_script("return typeof jQuery !== 'undefined'")
        )
        logging.info("jQuery loaded successfully")
        
        # کلیک روی دکمه پوکر
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/main/div[1]/article/main/section[3]/div[1]/div[2]/a[1]'))
        ).click()
        logging.info("Clicked on poker button")
        
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
            sleep(4)
            
            # کلیک روی لینک تورنمنت‌ها
            try:
                # اول با سلکتور CSS امتحان می‌کنی
                logging.info("Trying to find tournament link...")
                tournament_link = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".category__link[href='/tournaments']"))
                )
                logging.info("Tournament link found")
                
                # کمی صبر می‌کنیم
                sleep(2)
                
                # اول با جاوااسکیپت امتحان می‌کنیم
                try:
                    driver.execute_script("arguments[0].click();", tournament_link)
                    logging.info("Clicked tournament link with JavaScript")
                except Exception as js_error:
                    logging.warning(f"JavaScript click failed: {js_error}")
                    
                    # اگر جاوااسکریپت کار نکرد، با اکشن امتحان می‌کنیم
                    try:
                        from selenium.webdriver.common.action_chains import ActionChains
                        actions = ActionChains(driver)
                        actions.move_to_element(tournament_link)
                        actions.click()
                        actions.perform()
                        logging.info("Clicked tournament link with Action Chains")
                    except Exception as action_error:
                        logging.warning(f"Action Chains click failed: {action_error}")
                        
                        # در نهایت کلیک معمولی
                        tournament_link.click()
                        logging.info("Clicked tournament link with normal click")
                
                # صبر برای تغییر صفحه
                sleep(3)
                
                # تایید موفقیت‌آمیز بودن کلیک
                WebDriverWait(driver, 10).until(
                    lambda x: "tournament" in driver.current_url.lower() or 
                             len(driver.find_elements(By.CLASS_NAME, "tournament-list")) > 0
                )
                logging.info("Successfully navigated to tournament page")
                
                # ثبت‌نام در تورنمنت
                registration_result = handle_tournament_registration(driver, username)
                
                # ذخیره نتیجه یا ارسال به سیسم دیگر
                logging.info(f"Tournament registration completed: {registration_result}")
                
            except Exception as e:
                logging.error(f"Error in Poker account: {e}")
                return
            
        except Exception as e:
            logging.error(f"Error in Iframe account: {e}")
            return

        
    except Exception as e:
        logger.error(f"Error processing account: {e}")
        raise  # اجازه میدیم خطا به دکوریتور برسه
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Driver closed")
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")

def handle_tournament_registration(driver, username):
    try:
        logging.info("Starting tournament registration process...")
        
        # صبر برای لود شدن لیست تورنمنت‌ها
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "tournaments-list__item"))
        )
        logging.info("Tournament list loaded")
        
        # گرفتن اطلاعات اولین ترنمنت
        first_tournament = driver.find_element(By.CLASS_NAME, "tournaments-list__item")
        tournament_info = {
            'date': first_tournament.find_element(By.CLASS_NAME, "tournaments-list__date").text,
            'name': first_tournament.find_element(By.CLASS_NAME, "tournaments-list__name-text").text,
            'players': first_tournament.find_element(By.CLASS_NAME, "tournaments-list__player-count").text,
            'buyin': first_tournament.find_element(By.CLASS_NAME, "tournaments-list__buyin-text").text,
            'prize': first_tournament.find_element(By.CLASS_NAME, "tournaments-list__prize-text").text
        }
        logging.info(f"Tournament details: {tournament_info}")
        
        try:
            # بررسی دکمه unregister
            unregister_button = first_tournament.find_element(By.CSS_SELECTOR, "button.error")
            logging.info("Found unregister button - User is already registered")

            update_account_info(
                ACCOUNTS_FILE,
                username,
                registered=True,
                tournament_name=tournament_info['name']
            )

            return {
                'status': 'already_registered',
                'tournament': tournament_info,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception:
            try:
                # کلیک روی دکمه register
                register_button = first_tournament.find_element(By.CSS_SELECTOR, "button.tournaments__right-register")
                logging.info("Found register button - Proceeding with registration")
                register_button.click()
                logging.info("Clicked first register button")
                sleep(2)
                
                # منتظر باز شدن فریم و کلیک روی دکمه register داخل فریم
                register_confirm = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div/div[2]/div/view/div/div[2]/button'))
                )
                register_confirm.click()
                logging.info("Clicked register confirm button")
                sleep(2)
                
                # منتظر تغییر محتوای فریم و کلیک روی دکمه OK
                ok_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div/div[2]/div/view/div/div[2]/button'))
                )
                ok_button.click()
                logging.info("Clicked final OK button")
                sleep(2)
                
                # بروزرسانی اطلاعات در فایل اکسل
                update_account_info(
                    ACCOUNTS_FILE,
                    username,
                    registered=True,
                    tournament_name=tournament_info['name']
                )
                
                return {
                    'status': 'success',
                    'tournament': tournament_info,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
            except Exception as e:
                logging.error(f"Error during registration process: {e}")
                return {
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
    except Exception as e:
        logging.error(f"Error during tournament registration: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

def update_account_info(excel_path, username, poker_balance=None, poker_game_balance=None, 
                       casino_balance=None, registered=None, tournament_name=None, last_check_time=None):
    try:
        df = pd.read_excel(excel_path)
        
        # آپدیت اطلاعات موجد
        if poker_balance is not None:
            df.loc[df['username'] == username, 'poker_balance'] = poker_balance
        if poker_game_balance is not None:
            df.loc[df['username'] == username, 'poker_game_balance'] = poker_game_balance
        if casino_balance is not None:
            df.loc[df['username'] == username, 'casino_balance'] = casino_balance
        if registered is not None:
            df.loc[df['username'] == username, 'registered'] = registered
        if tournament_name is not None:
            df.loc[df['username'] == username, 'registered_tournament'] = tournament_name
        if last_check_time is not None:
            df.loc[df['username'] == username, 'last_check_time'] = last_check_time
            
        # ذخیره فایل
        df.to_excel(excel_path, index=False)
        main_logger.success(f"Successfully updated info for {username}")
        
    except Exception as e:
        main_logger.error(f"Error updating Excel file: {e}")
        raise

# خواندن فایل اکانت‌ها
def read_accounts(excel_path):
    try:
        df = pd.read_excel(excel_path)
        accounts = []
        
        for _, row in df.iterrows():
            try:
                # تبدیل تاریخ و زمان به فرمت استاندارد
                start_datetime = None
                if pd.notna(row['start_time']):
                    try:
                        # تلاش برای خواندن تاریخ و زمان کامل
                        start_datetime = pd.to_datetime(str(row['start_time']))
                    except ValueError:
                        try:
                            # اگر فقط زمان وارد شده بود، تاریخ امروز رو اضافه می‌کنیم
                            time_str = str(row['start_time']).strip()
                            today = datetime.now().date()
                            start_datetime = datetime.combine(today, datetime.strptime(time_str, '%H:%M:%S').time())
                        except ValueError:
                            logging.warning(f"Invalid start_time format for user {row['username']}, setting to None")
                            start_datetime = None

                account = {
                    'username': str(row['username']),
                    'password': str(row['password']),
                    'start_time': start_datetime,  # حالا به جای time از datetime استفاده می‌کنیم
                    'registered': bool(row['registered']) if pd.notna(row['registered']) else False,
                    'registered_tournament': str(row['registered_tournament']) if pd.notna(row['registered_tournament']) else None,
                    'poker_balance': float(row['poker_balance']) if pd.notna(row['poker_balance']) else 0.0,
                    'poker_game_balance': float(row['poker_game_balance']) if pd.notna(row['poker_game_balance']) else 0.0,
                    'casino_balance': float(row['casino_balance']) if pd.notna(row['casino_balance']) else 0.0,
                    'last_check_time': str(row['last_check_time']) if pd.notna(row['last_check_time']) else None
                }
                accounts.append(account)
                
            except Exception as e:
                logging.error(f"Error processing row for user {row['username']}: {e}")
                continue
                
        logging.info(f"Successfully loaded {len(accounts)} accounts from Excel file")
        return accounts
        
    except Exception as e:
        logging.error(f"Error reading Excel file: {e}")
        raise

def schedule_jobs(accounts, threads):
    immediate_accounts = [acc for acc in accounts if acc['start_time'] is None]
    scheduled_accounts = [acc for acc in accounts if acc['start_time'] is not None]
    
    logger = logging.getLogger('Scheduler')
    
    # اجرای فوری اکانت‌های بدون زمان‌بندی
    if immediate_accounts:
        logger.info(f"Starting immediate execution for {len(immediate_accounts)} accounts...")
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [executor.submit(login_and_register, account) for account in immediate_accounts]
            
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Task failed completely: {e}")
                    continue
                    
        logger.info("Immediate executions completed")
    
    # اجرای زمان‌بندی شده
    if scheduled_accounts:
        logger.info(f"Waiting for scheduled time for {len(scheduled_accounts)} accounts...")
        while True:
            current_datetime = datetime.now()
            ready_accounts = [acc for acc in scheduled_accounts if acc['start_time'] <= current_datetime]
            
            if ready_accounts:
                logger.info(f"Starting execution for {len(ready_accounts)} scheduled accounts...")
                with ThreadPoolExecutor(max_workers=threads) as executor:
                    futures = [executor.submit(login_and_register, account) for account in ready_accounts]
                    
                    for future in futures:
                        try:
                            future.result()
                        except Exception as e:
                            logger.error(f"Scheduled task failed completely: {e}")
                            continue
                
                scheduled_accounts = [acc for acc in scheduled_accounts if acc not in ready_accounts]
            
            if not scheduled_accounts:
                logger.info("All scheduled accounts have been processed")
                break
                
            sleep(30)

def check_balance(driver, username, logger, account):
    try:
        # کلیک روی دراپ‌داون بالانس
        balance_dropdown = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "headerBalances"))
        )
        balance_dropdown.click()
        logger.info("Balance dropdown clicked")
        sleep(2)
        
        # خبر برای لود شدن بالانس‌ها
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "dropdownBalanceList"))
        )
        
        # صبر اضافی برای اطمینان از لود کامل مقادیر
        sleep(3)
        
        # خواندن بالانس‌ها
        balances = {
            'poker': driver.find_element(By.XPATH, "//div[@id='dropdownBalanceList']//p[1]/small").text.strip(),
            'poker_game': driver.find_element(By.XPATH, "//div[@id='dropdownBalanceList']//p[2]/small").text.strip(),
            'casino': driver.find_element(By.XPATH, "//div[@id='dropdownBalanceList']//p[3]/small").text.strip()
        }
        
        # حذف TRY و تبدیل به float
        for key in balances:
            balances[key] = float(balances[key].replace('TRY', '').replace(',', '.').strip())
        
        # آپدیت در اکسل
        update_account_info(
            ACCOUNTS_FILE,
            username,
            poker_balance=balances['poker'],
            poker_game_balance=balances['poker_game'],
            casino_balance=balances['casino'],
            last_check_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        # نمایش در کنسول
        logger.success(f"""
Balance Report for {username}:
🎲 Poker Balance: {balances['poker']} TRY
🎮 Poker Game Balance: {balances['poker_game']} TRY
🎰 Casino Balance: {balances['casino']} TRY
        """)
        
        return balances
        
    except Exception as e:
        logger.error(f"Error checking balance: {str(e)}")
        return None

def create_excel_if_not_exists(excel_path):
    try:
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        
        if not os.path.exists(excel_path):
            # ساخت دیتافریم با ستون‌های مورد نیاز و تعیین نوع داده‌ها
            df = pd.DataFrame(columns=[
                'username',
                'password',
                'start_time',
                'Balance',
                'registered',
                'registered_tournament',
                'poker_balance',
                'poker_game_balance',
                'casino_balance',
                'last_check_time'
            ]).astype({
                'username': 'str',
                'password': 'str',
                'start_time': 'object',
                'Balance': 'float64',
                'registered': 'bool',  # تغییر به boolean
                'registered_tournament': 'str',  # تغییر به string
                'poker_balance': 'float64',
                'poker_game_balance': 'float64',
                'casino_balance': 'float64',
                'last_check_time': 'object'
            })
            
            # ذخیره فایل
            df.to_excel(excel_path, index=False)
            logging.info(f"Created new Excel file at {excel_path}")
            return True
            
        return False
        
    except Exception as e:
        logging.error(f"Error creating Excel file: {e}")
        raise

def print_banner():
     banner = """
                                                
        🌟 Poker Tournament Registration Bot
        📚 Github - github.com/pllusin
"""


# ██████╗ ██╗     ██╗   ██╗███████╗██╗███╗   ██╗
# ██╔══██╗██║     ██║   ██║██╔════╝██║████╗  ██║
# ██████╔╝██║     ██║   ██║███████╗██║██╔██╗ ██║
# ██╔═══╝ ██║     ██║   ██║╚════██║██║██║╚██╗██║
# ██║     ███████╗╚██████╔╝███████║██║██║ ╚████║
# ╚═╝     ╚══════╝ ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝
    # چاپ بنر با رنگ سبز
    # print(colored(banner, 'green', attrs=['bold']))

# جرای اصلی
if __name__ == "__main__":
    print_banner()
    setup_logging()  # تنظیم لاگینگ در ابتدای برنامه
    
    # پردازش هر فایل اکسل به ترتیب
    for excel_file in ACCOUNTS_FILE:
        main_logger.info(f"Processing Excel file: {excel_file}")
        
        try:
            create_excel_if_not_exists(excel_file)
            accounts = read_accounts(excel_file)
            main_logger.info(f"Loaded {len(accounts)} accounts from {excel_file}")
            
            if RUN_EVENT:
                main_logger.info("Running tournament registration...")
                schedule_jobs(accounts, THREADS)
                
            if CHECK_BALANCE:
                main_logger.info("Running balance check...")
                # برای چک بالانس، همه اکانت‌ها را مستقیماً پردازش می‌کنیم
                with ThreadPoolExecutor(max_workers=THREADS) as executor:
                    futures = [executor.submit(login_and_register, account) for account in accounts]
                    for future in futures:
                        try:
                            future.result()
                        except Exception as e:
                            main_logger.error(f"Task failed: {e}")
                            continue
                            
        except Exception as e:
            main_logger.error(f"Error processing file {excel_file}: {e}")
            continue
            
    main_logger.success("All Excel files processed successfully")

