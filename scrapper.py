
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

import logging

class BGA_Page:
    def __init__(self, url, logger=logging.getLogger()):
        # self.logger = logging.getLogger('selenium.webdriver.remote.remote_connection')
        # self.logger.setLevel(logging.CRITICAL)  # or any variant from ERROR, CRITICAL or NOTSET
        self.logger = logger
        self.url = url

        # Set options for WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Ensure GUI is off
        chrome_options.add_argument("--no-sandbox")  # Bypass OS security model, REQUIRED on Linux
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
        chrome_options.add_argument("--log-level=3")  # Overcome limited resource problems
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        # Initialize the WebDriver with options
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(20)

    def get_page(self):
        try:
            # Open the URL
            self.driver.get(self.url)
            return 0
        except Exception as e:
            return e
        
    def check_whos_up(self):
        try:
            # Now that the page is loaded, find the elements as before.
            player_boards = self.driver.find_elements(By.CLASS_NAME, "player-board")
            for player_board in player_boards:
                active_player_img = player_board.find_elements(By.XPATH, ".//img[contains(@src, 'active_player') and substring(@src, string-length(@src) - 3) = '.gif']")
                # print(f"id={player_board.get_attribute("id")}; len={len(active_player_img)}")
                for img in active_player_img:
                    # Check if the parent element does not have "display:none" style.
                    parent = img.find_element(By.XPATH, "..")
                    # print(f"style: {parent.get_attribute('style').replace(" ","")}")
                    if "display:none" not in parent.get_attribute('style').replace(" ",""):
                        player_name_element = player_board.find_element(By.CLASS_NAME, "player-name")
                        # print(player_name_element.text.strip())
                        return player_name_element.text.strip()
            # print("player not found")
            return None
        except:
            return 1
    
    def close(self):   
        self.driver.quit()
