
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import logging
import time

class BGA_Page:
    def __init__(self, url, logger=logging.getLogger()):
        logger = logging.getLogger('selenium.webdriver.remote.remote_connection')
        logger.setLevel(logging.CRITICAL)  # or any variant from ERROR, CRITICAL or NOTSET

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
        
        # Open the URL
        self.driver.get(url)
        
    def check_whos_up(self):

        # Now that the page is loaded, find the elements as before.
        player_boards = self.driver.find_elements(By.CLASS_NAME, "player-board")

        for player_board in player_boards:
            active_player_img = player_board.find_elements(By.XPATH, ".//img[@src='https://x.boardgamearena.net/data/themereleases/240320-1000/img/layout/active_player.gif']")
            for img in active_player_img:
                # Check if the parent element does not have "display:none" style.
                parent = img.find_element(By.XPATH, "..")
                if "display:none" not in parent.get_attribute('style').replace(" ",""):
                    player_name_element = player_board.find_element(By.CLASS_NAME, "player-name")
                    return player_name_element.text.strip()
        return None
    
    def close(self):   
        self.driver.quit()