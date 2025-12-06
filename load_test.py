from locust import HttpUser, task, between
import random
import os

class DocuScanUser(HttpUser):
    host = "https://docuscan-api-907479741506.us-central1.run.app"  # Class-level host
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        # List of test PNGs (cycles through 10 for 50 uploads)
        self.png_files = [f'test_pngs/test{i}.png' for i in range(1, 11)]
        if not os.path.exists(self.png_files[0]):
            raise Exception("Generate PNGs first: python generate_test_pngs.py")
    
    @task
    def upload_png(self):
        # Pick random PNG
        filename = random.choice(self.png_files)
        
        with open(filename, 'rb') as img_file:
            files = {'file': (os.path.basename(filename), img_file, 'image/png')}
            response = self.client.post('/upload', files=files)
        
        if response.status_code != 202:
            response.failure(f"Upload failed: {response.status_code}")