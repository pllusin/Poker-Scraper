from selenium import webdriver
from selenium.webdriver.firefox.options import Options

options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Firefox(options=options)

driver.get("https://www.google.com")
input("Press Enter to close...")
driver.quit()
