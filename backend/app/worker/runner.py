import time



def run_forever():
    # Core AI suggestions are now triggered by FastAPI BackgroundTasks.
    # Worker process remains available for future extension jobs.
    while True:
        time.sleep(5)


if __name__ == '__main__':
    run_forever()
