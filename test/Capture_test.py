import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
import cv2

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("キャプチャテストアプリ")
        self.master.geometry("500x700")  # ウィンドウのサイズを設定 (幅x高さ)
        self.pack()

        self.create_widgets()

        # キャプチャーボードの初期化
        self.cap = cv2.VideoCapture(0)  # カメラまたはキャプチャーボードのインデックス (0 は通常最初のデバイス)

    def create_widgets(self):
        # 画像表示エリア
        self.image_frame = tk.Frame(self)
        self.image_frame.pack()

        self.image_label = tk.Label(self.image_frame)
        self.image_label.pack()

        # キャプチャボタン
        self.capture_button = tk.Button(self, text="キャプチャ", command=self.capture_image)
        self.capture_button.pack(pady=10)

    def capture_image(self):
        # フレームを取得
        ret, frame = self.cap.read()
        if ret:
            # フレームを PIL Image に変換
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            image.thumbnail((300, 300))  # 画像のサイズ調整
            photo = ImageTk.PhotoImage(image)
            self.image_label.config(image=photo)
            self.image_label.image = photo

if __name__ == "__main__":
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()