import io
import re
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk, ImageFilter
from google.cloud import vision
from multiprocessing import Process, Queue

def detect_text(image_bytes):
    """Google Vision API を使用して画像からテキストを抽出する."""
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description.split('\n') if texts else []

def group_players_by_team(player_names, prefix_length=1):
    """プレイヤー名を接頭辞でグループ化し、チーム辞書を作成する."""
    teams = {}
    for name in player_names:
        prefix = name[:prefix_length].lower()
        if prefix not in teams:
            teams[prefix] = []
        teams[prefix].append(name)
    return teams

def calculate_team_scores(teams, race_scores):
    """チームごとの合計得点を算出する."""
    team_scores = {}
    for team_name, player_names in teams.items():
        team_scores[team_name] = 0
        for player_name in player_names:
            team_scores[team_name] += race_scores.get(player_name, 0)

def process_image(image_path, queue):
    """画像処理とテキスト認識を行う関数 (別のプロセスで実行)"""
    try:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
        player_names = extract_player_names(image_bytes)  # テキスト認識を行う
        queue.put(player_names)  # 結果をキューに入れる
    except Exception as e:
        print(f"画像処理中にエラーが発生しました: {e}")
        queue.put(None)  # エラーが発生した場合は None を入れる

def extract_player_names(image_bytes):
    """画像からプレイヤー名を抽出する."""
    player_names = []
    try:
        image = Image.open(io.BytesIO(image_bytes))

        # プレイヤー名領域を定義 (画像サイズに合わせて調整が必要)
        player_name_area = (1014, 80, 1431, 1000)

        # 各プレイヤー名の画像からテキスト認識を行う (並列処理ではない)
        for i in range(12):
            try:
                player_name_img = image.crop(
                    (
                        player_name_area[0],
                        player_name_area[1]
                        + i * (player_name_area[3] - player_name_area[1]) // 12,
                        player_name_area[2],
                        player_name_area[1]
                        + (i + 1) * (player_name_area[3] - player_name_area[1]) // 12,
                    )
                )

                # 画像をメモリ上に保存
                img_byte_arr = io.BytesIO()
                player_name_img.save(img_byte_arr, format="PNG")
                img_byte_arr = img_byte_arr.getvalue()

                detected_texts = detect_text(img_byte_arr)
                if detected_texts:
                    player_names.append(detected_texts[0])
            except IndexError:
                break
    except Exception as e:
        print(f"画像処理中にエラーが発生しました: {e}")
    return player_names

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("マリオカート チーム戦 集計アプリ")
        self.master.geometry("500x400")  # ウインドウのサイズを設定 (幅x高さ)
        self.pack()

        self.current_race = -1  # 現在のレース番号 (初期値は -1)

        self.create_widgets()

        self.team_total_scores = {}  # 全レースのチームごとの合計得点を格納
        self.race_results = []  # 各レースの結果を格納

    def create_widgets(self):
        # レース番号表示ラベル
        self.race_label = tk.Label(self, text=f"現在のレース: {self.current_race + 1}")
        self.race_label.pack(pady=5)

        # 画像選択ボタン
        self.select_image_button = tk.Button(self, text="画像を選択", command=self.select_image)
        self.select_image_button.pack(pady=10)

        # 集計結果表示エリア
        self.result_frame = tk.Frame(self)
        self.result_frame.pack()

        # チームごとの得点表示 (Treeviewを使用)
        self.score_treeview = ttk.Treeview(self.result_frame, columns=("Rank", "Team", "Score"), show="headings")
        self.score_treeview.heading("Rank", text="順位", anchor="center")
        self.score_treeview.heading("Team", text="チーム")
        self.score_treeview.heading("Score", text="得点", anchor="center")
        self.score_treeview.column("Rank", width=50, anchor="center")  # 順位列の幅を設定
        self.score_treeview.column("Score", width=100, anchor="center")
        self.score_treeview.pack()

        # Treeviewのアイテム編集
        self.score_treeview.bind("<Double-1>", self.edit_score)

    def select_image(self):
        # ファイル選択ダイアログを開く
        file_path = filedialog.askopenfilename(
            initialdir=".",
            title="リザルト画像を選択",
            filetypes=(("Image files", "*.png;*.jpg;*.jpeg"), ("all files", "*.*"))
        )
        if not file_path:
            return

        # 別のプロセスで画像処理を実行
        queue = Queue()
        p = Process(target=process_image, args=(file_path, queue))
        p.start()

        # 結果を取得して処理
        player_names = queue.get()
        if player_names is not None:
            self.process_race_results(player_names)
        else:
            print("画像処理中にエラーが発生しました。")
        p.join()  # プロセスが終了するまで待つ

    def process_race_results(self, player_names):
        """レース結果を処理し、チームごとの得点を計算する."""
        race_scores = {}
        for rank, name in enumerate(player_names):
            if rank == 0:
                score = 15
            elif rank == 1:
                score = 12
            else:
                score = 12 - rank
            team_name = name[0].lower()  # チーム名は先頭1文字として取得
            if team_name not in race_scores:
                race_scores[team_name] = 0
            race_scores[team_name] += score

        # レース結果を保存
        self.race_results.append((player_names, race_scores))  # race_results に追加

        # チームごとの合計得点を更新
        for team_name, score in race_scores.items():
            if team_name in self.team_total_scores:
                self.team_total_scores[team_name] += score
            else:
                self.team_total_scores[team_name] = score

        self.current_race += 1  # レース番号をインクリメント
        self.update_race_label()  # レース番号のラベルを更新
        self.update_result_display()  # 集計結果を更新

    def update_race_label(self):
        """レース番号のラベルを更新する."""
        self.race_label.config(text=f"現在のレース: {self.current_race + 1}")

    def update_result_display(self):
        """集計結果表示を更新する."""
        # Treeviewをクリア
        for item in self.score_treeview.get_children():
            self.score_treeview.delete(item)

        # チームごとの合計得点を計算し、ソート
        sorted_team_scores = sorted(self.team_total_scores.items(), key=lambda x: x[1], reverse=True)

        # Treeviewのスタイル設定
        style = ttk.Style()
        style.configure("Treeview.Heading", font=("Helvetica", 12, "bold"))  # ヘッダーフォント
        style.configure("Treeview", font=("Helvetica", 10))  # 通常のフォント
        style.configure("PointDiff.Treeview", font=("Helvetica", 10, "bold"))  # 点差フォント

        # 順位、チーム、得点を表示
        previous_score = None
        rank = 1
        for i, (team_name, score) in enumerate(sorted_team_scores):
            # 同点の場合は同じ順位を表示
            if score == previous_score:
                ranking_text = f"{rank}位"
            else:
                ranking_text = f"{i + 1}位"
                rank = i + 1
            previous_score = score

            # 1番目のチームは点差行を挿入しない
            if i > 0:
                # 前のチームとの点差を計算
                point_diff = score - sorted_team_scores[i - 1][1]
                # 点差行の挿入 (スタイルを適用)
                self.score_treeview.insert(
                    "", "end", values=("", "", f"±{abs(point_diff)}"), tags=("PointDiff",)
                )  # abs() で絶対値を取得

            # チーム情報行の挿入
            self.score_treeview.insert("", "end", values=(ranking_text, team_name, score))

        # タグのスタイル設定を適用
        self.score_treeview.tag_configure("PointDiff", font=("Helvetica", 10, "bold"))

        # Treeviewの縦幅を調整
        self.score_treeview.config(height=11)  # 11行表示するように変更

    def edit_score(self, event):
        """Treeviewのアイテムをダブルクリックした際に編集モードに移行"""
        item = self.score_treeview.identify_row(event.y)
        if item:
            # ダブルクリックされたアイテムのインデックスを取得
            column = self.score_treeview.identify_column(event.x)
            if column == "#3":  # 得点の列のみ編集可能
                # 編集用のEntryウィジェットを作成
                entry = tk.Entry(self.score_treeview)
                entry.insert(0, self.score_treeview.item(item, "values")[2])  # 現在の値を表示
                entry.pack()

                # EntryウィジェットをTreeview内に配置
                entry.place(x=event.x, y=event.y, anchor="w")

                def confirm_edit(event=None):
                    """編集内容を確定し、Entryウィジェットを削除"""
                    new_score = entry.get()
                    try:
                        new_score = int(new_score)  # 整数に変換
                        self.score_treeview.item(item, values=(self.score_treeview.item(item, "values")[0], self.score_treeview.item(item, "values")[1], new_score))
                        # チームごとの合計得点を更新
                        team_name = self.score_treeview.item(item, "values")[1]
                        self.team_total_scores[team_name] = new_score
                        self.update_result_display()  # Treeviewを更新
                    except ValueError:
                        # 無効な入力値の場合の処理
                        pass
                    entry.destroy()

                entry.bind("<Return>", confirm_edit)  # Enterキーで確定
                entry.bind("<FocusOut>", confirm_edit)  # フォーカスが外れたら確定
                entry.focus_set()  # Entryにフォーカスを設定

if __name__ == "__main__":
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()