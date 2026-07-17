import os

class Config:

    UPLOAD_FOLDER = "data/uploads"

    PDF_FOLDER = "data/pdfs"

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    @staticmethod
    def create_directories():

        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

        os.makedirs(Config.PDF_FOLDER, exist_ok=True)