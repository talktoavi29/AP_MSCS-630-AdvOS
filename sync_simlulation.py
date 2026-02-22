import threading
import time
from queue import Queue

class ProducerConsumerDemo:

    def __init__(self, buffer_size=5):
        self.buffer = Queue(buffer_size)
        self.mutex = threading.Semaphore(1)
        self.empty = threading.Semaphore(buffer_size)
        self.full = threading.Semaphore(0)

    def producer(self, items=5):
        for i in range(items):
            self.empty.acquire()
            self.mutex.acquire()

            item = f"item-{i}"
            self.buffer.put(item)
            print("Produced:", item)

            self.mutex.release()
            self.full.release()
            time.sleep(1)

    def consumer(self, items=5):
        for i in range(items):
            self.full.acquire()
            self.mutex.acquire()

            item = self.buffer.get()
            print("Consumed:", item)

            self.mutex.release()
            self.empty.release()
            time.sleep(1)

    def run_demo(self):
        p = threading.Thread(target=self.producer)
        c = threading.Thread(target=self.consumer)
        p.start()
        c.start()
        p.join()
        c.join()