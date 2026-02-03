from dataclasses import dataclass, field
from collections import deque
import heapq
import time
from typing import List, Dict, Optional, Tuple


@dataclass
class SimProcess:
    pid: int
    name: str
    burst: int                 
    priority: int             
    arrival: int = 0          
    remaining: int = field(init=False)

    # Metrics
    first_start: Optional[int] = None
    finish_time: Optional[int] = None

    def __post_init__(self):
        self.remaining = self.burst


class SchedulerSim:
    """
    Simulates CPU scheduling inside the shell.
    Uses discrete time "ticks". You can slow it down with tick_sleep for screenshots.
    """

    def __init__(self):
        self._next_pid = 1
        self._procs: List[SimProcess] = []  

    def reset(self):
        self._next_pid = 1
        self._procs.clear()

    def add_process(self, name: str, burst: int, priority: int, arrival: int = 0) -> SimProcess:
        if burst <= 0:
            raise ValueError("burst must be > 0")
        if priority < 0:
            raise ValueError("priority must be >= 0")
        if arrival < 0:
            raise ValueError("arrival must be >= 0")

        p = SimProcess(pid=self._next_pid, name=name, burst=burst, priority=priority, arrival=arrival)
        self._next_pid += 1
        self._procs.append(p)
        return p

    def list_processes(self) -> List[SimProcess]:
        # Show in a stable order
        return sorted(self._procs, key=lambda x: x.pid)

    @staticmethod
    def _compute_metrics(p: SimProcess) -> Dict[str, int]:

        response = (p.first_start - p.arrival) if p.first_start is not None else -1
        turnaround = (p.finish_time - p.arrival) if p.finish_time is not None else -1
        waiting = turnaround - p.burst if turnaround >= 0 else -1
        return {"response": response, "turnaround": turnaround, "waiting": waiting}

    def _print_metrics(self, finished: List[SimProcess]):
        print("\n=== Performance Metrics (ticks) ===")
        print(f"{'PID':<5}{'Name':<10}{'Arr':<6}{'Burst':<7}{'Start':<7}{'Finish':<7}{'Resp':<7}{'Wait':<7}{'TAT':<7}")

        resp_sum = wait_sum = tat_sum = 0
        for p in finished:
            m = self._compute_metrics(p)
            resp_sum += m["response"]
            wait_sum += m["waiting"]
            tat_sum += m["turnaround"]
            print(f"{p.pid:<5}{p.name:<10}{p.arrival:<6}{p.burst:<7}"
                  f"{p.first_start:<7}{p.finish_time:<7}{m['response']:<7}{m['waiting']:<7}{m['turnaround']:<7}")

        n = len(finished)
        if n > 0:
            print("\nAverages:")
            print(f"  Avg response time   = {resp_sum / n:.2f}")
            print(f"  Avg waiting time    = {wait_sum / n:.2f}")
            print(f"  Avg turnaround time = {tat_sum / n:.2f}")


    def schedule_round_robin(self, quantum: int, tick_sleep: float = 0.0):
        if quantum <= 0:
            raise ValueError("quantum must be > 0")

        for p in self._procs:
            p.remaining = p.burst
            p.first_start = None
            p.finish_time = None

        time_now = 0
        finished: List[SimProcess] = []

        not_arrived = sorted(self._procs, key=lambda x: (x.arrival, x.pid))
        ready = deque()

        def push_arrivals(current_time: int):
            nonlocal not_arrived
            while not_arrived and not_arrived[0].arrival <= current_time:
                ready.append(not_arrived.pop(0))

        push_arrivals(time_now)

        print("\n=== Round Robin Scheduling ===")
        print(f"Quantum = {quantum} ticks, tick_sleep = {tick_sleep}")

        while ready or not_arrived:
            if not ready:
                next_t = not_arrived[0].arrival
                print(f"[t={time_now}] CPU idle -> jump to t={next_t}")
                time_now = next_t
                push_arrivals(time_now)
                continue

            p = ready.popleft()
            if p.first_start is None:
                p.first_start = time_now

            run_for = min(quantum, p.remaining)
            print(f"[t={time_now}] RUN  pid={p.pid}({p.name}) for {run_for} tick(s)  remaining={p.remaining}")

            for _ in range(run_for):
                time_now += 1
                p.remaining -= 1
                push_arrivals(time_now)
                if tick_sleep > 0:
                    time.sleep(tick_sleep)

                if p.remaining == 0:
                    p.finish_time = time_now
                    finished.append(p)
                    print(f"[t={time_now}] DONE pid={p.pid}({p.name})")
                    break

            if p.remaining > 0:
                ready.append(p)

        finished.sort(key=lambda x: x.finish_time)
        self._print_metrics(finished)


    def schedule_priority_preemptive(self, tick_sleep: float = 0.0):
        for p in self._procs:
            p.remaining = p.burst
            p.first_start = None
            p.finish_time = None

        time_now = 0
        finished: List[SimProcess] = []

        not_arrived = sorted(self._procs, key=lambda x: (x.arrival, x.pid))

        heap: List[Tuple[int, int, SimProcess]] = []

        def push_arrivals(current_time: int):
            nonlocal not_arrived
            while not_arrived and not_arrived[0].arrival <= current_time:
                p = not_arrived.pop(0)
                heapq.heappush(heap, (p.priority, p.pid, p))

        push_arrivals(time_now)
        running: Optional[SimProcess] = None

        print("\n=== Priority Scheduling (Preemptive) ===")
        print(f"Lower number = higher priority, tick_sleep = {tick_sleep}")

        while heap or not_arrived or running:
            if running is None and not heap:
                next_t = not_arrived[0].arrival
                print(f"[t={time_now}] CPU idle -> jump to t={next_t}")
                time_now = next_t
                push_arrivals(time_now)

            if running is None and heap:
                _, _, running = heapq.heappop(heap)
                if running.first_start is None:
                    running.first_start = time_now
                print(f"[t={time_now}] PICK pid={running.pid}({running.name}) prio={running.priority}")

            if running is not None:
                print(f"[t={time_now}] RUN  pid={running.pid}({running.name}) prio={running.priority} remaining={running.remaining}")
                time_now += 1
                running.remaining -= 1
                if tick_sleep > 0:
                    time.sleep(tick_sleep)

                push_arrivals(time_now)

                if running.remaining == 0:
                    running.finish_time = time_now
                    print(f"[t={time_now}] DONE pid={running.pid}({running.name})")
                    finished.append(running)
                    running = None
                    continue

                if heap:
                    top_prio, _, _ = heap[0]
                    if top_prio < running.priority:
                        print(f"[t={time_now}] PREEMPT pid={running.pid}({running.name}) -> higher priority arrived")
                        heapq.heappush(heap, (running.priority, running.pid, running))
                        running = None

        finished.sort(key=lambda x: x.finish_time)
        self._print_metrics(finished)
