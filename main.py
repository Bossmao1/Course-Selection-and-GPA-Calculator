from gui import CourseSelectionApp
from core import DEFAULT_CONFIG_PATH

def main():
    app = CourseSelectionApp(DEFAULT_CONFIG_PATH)
    app.mainloop()

if __name__ == "__main__":
    main()
