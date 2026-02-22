from collections import deque, OrderedDict

class MemoryManager:
    """
    Simple paging-based memory manager with FIFO and LRU replacement.
    """

    def __init__(self, num_frames=4, policy="FIFO"):
        self.num_frames = num_frames
        self.policy = policy.upper()
        self.frames = []
        self.page_faults = 0

        if self.policy == "FIFO":
            self.queue = deque()
        elif self.policy == "LRU":
            self.lru = OrderedDict()

    def set_policy(self, policy):
        self.policy = policy.upper()
        self.frames.clear()
        self.page_faults = 0
        self.queue = deque()
        self.lru = OrderedDict()

    def access_page(self, pid, page):
        key = (pid, page)

        # Page Hit
        if key in self.frames:
            if self.policy == "LRU":
                self.lru.move_to_end(key)
            print(f"HIT  -> Process {pid} Page {page}")
            return

        # Page Fault
        self.page_faults += 1
        print(f"FAULT -> Process {pid} Page {page}")

        if len(self.frames) >= self.num_frames:
            self.replace_page()

        self.frames.append(key)

        if self.policy == "FIFO":
            self.queue.append(key)
        else:
            self.lru[key] = True

    def replace_page(self):
        if self.policy == "FIFO":
            victim = self.queue.popleft()
        else:
            victim, _ = self.lru.popitem(last=False)

        self.frames.remove(victim)
        print(f"REPLACE -> Evicted {victim}")

    def status(self):
        print("\nFrames:")
        for f in self.frames:
            print(f)
        print("Page Faults:", self.page_faults)