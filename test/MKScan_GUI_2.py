import io
import re
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk, ImageFilter
from google.cloud import vision
from tkinter import ttk
import threading

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
                img_byte_arr = img_byte_arr.getvalue()  # バイナリデータを取得

                detected_texts = detect_text(img_byte_arr)
                if detected_texts:
                    player_names.append(detected_texts[0])

                # ここでプログレスバーを更新
                app.progress_bar["value"] += 1  # プログレスバーを1ステップ進める
                app.update_idletasks()  # GUI を更新

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
        self.master.geometry("500x700")  # ウィンドウのサイズを設定 (幅x高さ)
        self.pack()

        self.current_race = -1  # 現在のレース番号 (初期値は -1)
        self.image_paths = []  # レース結果画像のパスを格納するリスト
        self.current_image_index = -1  # 現在の表示画像のインデックス (初期値は -1)

        self.create_widgets()

        self.team_total_scores = {}  # 全レースのチームごとの合計得点を格納
        self.race_results = []  # 各レースの結果を格納
        self.undo_stack = []  # Undo 用のスタック

    def create_widgets(self):
        # レース番号表示ラベル
        self.race_label = tk.Label(self, text=f"現在のレース: {self.current_race + 1}")
        self.race_label.pack(pady=5)

        # 画像表示エリア
        self.image_frame = tk.Frame(self)
        self.image_frame.pack()

        self.image_label = tk.Label(self.image_frame)
        self.image_label.pack()

        # 画像選択ボタン
        self.select_image_button = tk.Button(self, text="画像を選択", command=self.select_image)
        self.select_image_button.pack(pady=10)

        # プログレスバー
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.pack(pady=5)

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

        # 左右の矢印ボタン
        self.prev_button = tk.Button(self, text="<<", command=self.show_prev_image, state=tk.DISABLED)
        self.prev_button.pack(side=tk.LEFT, padx=5)

        self.next_button = tk.Button(self, text=">>", command=self.show_next_image, state=tk.DISABLED)
        self.next_button.pack(side=tk.RIGHT, padx=5)

        # Undo ボタン
        self.undo_button = tk.Button(self, text="Undo", command=self.undo_score_change, state=tk.DISABLED)
        self.undo_button.pack(pady=5)

    def select_image(self):
        # ファイル選択ダイアログを開く
        file_path = filedialog.askopenfilename(
            initialdir=".",
            title="リザルト画像を選択",
            filetypes=(("Image files", "*.png;*.jpg;*.jpeg"), ("all files", "*.*"))
        )
        if not file_path:
            return

        # 画像のパスをリストに追加
        self.image_paths.append(file_path)

        # 現在の画像のインデックスを更新
        self.current_image_index += 1

        # プログレスバーをリセット
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = 12  # プレイヤーの数

        # 別のスレッドで画像処理を実行 (GUI をブロックしないように)
        def process_image_thread():
            try:
                with open(file_path, "rb") as image_file:
                    image_bytes = image_file.read()
                player_names = extract_player_names(image_bytes)  # テキスト認識を行う

                # プログレスバーを更新
                self.progress_bar["value"] = 12

                self.process_race_results(player_names)
                self.show_current_image()  # 画像を表示
            except Exception as e:
                print(f"画像処理中にエラーが発生しました: {e}")
                self.progress_bar["value"] = 12

        thread = threading.Thread(target=process_image_thread)
        thread.start()

        # 矢印ボタンの状態を更新
        self.update_button_states()

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
        sorted_team_scores = sorted(self.team_total_scores.items(), key=lambda x: int(x[1]), reverse=True) # 修正: int(x[1]) で値を int 型に変換

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
                        # Undo 用に元の値と新しい値をスタックに追加
                        self.undo_stack.append(
                            (
                                self.score_treeview.item(item, "values")[1],
                                self.score_treeview.item(item, "values")[2],
                                new_score,
                            )
                        )

                        self.score_treeview.item(item, values=(self.score_treeview.item(item, "values")[0], self.score_treeview.item(item, "values")[1], new_score))
                        # チームごとの合計得点を更新
                        team_name = self.score_treeview.item(item, "values")[1]
                        self.team_total_scores[team_name] = new_score
                        self.update_result_display()  # Treeviewを更新
                        self.undo_button.config(state=tk.NORMAL)  # Undo ボタンを有効化
                    except ValueError:
                        # 無効な入力値の場合の処理
                        pass
                    entry.destroy()

                entry.bind("<Return>", confirm_edit)  # Enterキーで確定
                entry.bind("<FocusOut>", confirm_edit)  # フォーカスが外れたら確定
                entry.focus_set()  # Entryにフォーカスを設定

    def show_current_image(self):
        """現在のレース結果画像を表示する."""
        if self.current_image_index >= 0 and self.current_image_index < len(self.image_paths):
            image_path = self.image_paths[self.current_image_index]
            try:
                image = Image.open(image_path)
                image.thumbnail((300, 300))  # 画像のサイズ調整
                photo = ImageTk.PhotoImage(image)
                self.image_label.config(image=photo)
                self.image_label.image = photo
            except Exception as e:
                print(f"画像の読み込みに失敗しました: {e}")

    def show_prev_image(self):
        """前のレース結果画像を表示する."""
        self.current_image_index -= 1
        self.show_current_image()
        self.update_button_states()

    def show_next_image(self):
        """次のレース結果画像を表示する."""
        self.current_image_index += 1
        self.show_current_image()
        self.update_button_states()

    def update_button_states(self):
        """矢印ボタンの状態を更新する."""
        if self.current_image_index <= 0:
            self.prev_button.config(state=tk.DISABLED)
        else:
            self.prev_button.config(state=tk.NORMAL)

        if self.current_image_index >= len(self.image_paths) - 1:
            self.next_button.config(state=tk.DISABLED)
        else:
            self.next_button.config(state=tk.NORMAL)

    def undo_score_change(self):
        """直前の得点変更を元に戻す."""
        if self.undo_stack:
            team_name, old_score, new_score = self.undo_stack.pop()
            # Treeview の項目を更新
            for item in self.score_treeview.get_children():
                if self.score_treeview.item(item, "values")[1] == team_name:
                    self.score_treeview.item(item, values=(self.score_treeview.item(item, "values")[0], team_name, old_score))
                    # 合計得点を元に戻す (ここで修正: old_score を int 型に変換)
                    self.team_total_scores[team_name] = int(old_score)
                    break

            # self.team_total_scores の値を int 型に変換してからソート
            sorted_team_scores = sorted(
                self.team_total_scores.items(), key=lambda x: int(x[1]), reverse=True
            )

            self.update_result_display()  # Treeview を更新
            if not self.undo_stack:  # スタックが空になったら Undo ボタンを無効化
                self.undo_button.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()