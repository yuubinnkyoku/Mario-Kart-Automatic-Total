import io
import re
from google.cloud import vision
from PIL import Image, ImageFilter

def detect_text(image_bytes):
    """Google Vision API を使用して画像からテキストを抽出する."""
    client = vision.ImageAnnotatorClient()

    # バイナリデータをVision API用のImageオブジェクトに変換
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
        team_scores[team_name] = 0  # 初期化
        for player_name in player_names:
            team_scores[team_name] += race_scores.get(player_name, 0)
    return team_scores

def main(image_paths):
    """メイン処理."""
    team_total_scores = {}  # チームごとの合計得点を格納する辞書

    # 各レースの結果処理
    for image_path in image_paths:
        # 1. リザルト画像の入力
        image = Image.open(image_path)

        # 2. プレイヤー名領域を定義
        player_name_area = (1014, 80, 1431, 1000)

        # 3. プレイヤー名を取得
        player_names = []
        for i in range(12):
            try:
                player_name_img = image.crop((player_name_area[0], player_name_area[1] + i * (player_name_area[3] - player_name_area[1]) // 12, player_name_area[2], player_name_area[1] + (i + 1) * (player_name_area[3] - player_name_area[1]) // 12))

                # 画像をメモリ上に保存
                img_byte_arr = io.BytesIO()
                player_name_img.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()

                #detect_textの結果の先頭要素のみを追加
                detected_texts = detect_text(img_byte_arr)
                if detected_texts:  # リストが空でないことを確認
                    player_names.append(detected_texts[0]) 
            except IndexError:
                break

        # 4. 順位に応じた得点をチームに付与
        race_scores = {}  # 各レースのチームごとの得点を格納する辞書
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
        
        # 5. チームごとの合計得点を更新
        for team_name, score in race_scores.items():
            if team_name in team_total_scores:
                team_total_scores[team_name] += score
            else:
                team_total_scores[team_name] = score

    # 6. 結果出力
    print("---- チームごとの合計得点 ----")
    sorted_team_scores = sorted(team_total_scores.items(), key=lambda x: x[1], reverse=True)
    for team_name, score in sorted_team_scores:
        print(f"{team_name}: {score}pt")

if __name__ == "__main__":
    image_paths = []
    while True:
        path = input("リザルト画像のパスを入力してください (終了するにはEnterキー): ")
        if not path:
            break
        image_paths.append(path)

    if image_paths:
        main(image_paths)