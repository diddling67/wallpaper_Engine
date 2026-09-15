import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    from ui.app import ArchImgApp

    app = ArchImgApp()
    app.mainloop()


if __name__ == "__main__":
    main()
