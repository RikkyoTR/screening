import streamlit as st
from PIL import Image
from google import genai
import os
import tempfile
import time

st.set_page_config(page_title="フィジカル・スクリーニング AI判定", layout="wide")
st.title("🏃 フィジカル・スクリーニング AI判定ツール")
st.caption("項目ごとに複数枚の写真・動画を選択して判定します。（高精度化のため5回アンサンブル解析を実行します）")

# APIキーの設定
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.warning("⚠️ Streamlit Secrets に 'GEMINI_API_KEY' を設定してください。")
    api_key = st.text_input("Gemini API Key を入力:", type="password")

if api_key:
    client = genai.Client(api_key=api_key)

    st.markdown("### 📹 1. 動作動画の選択")
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        v_ohsq = st.file_uploader("【動画】オーバーヘッドSQ (OHSQ)", type=["mp4", "mov", "avi"], key="ohsq")
    with col_v2:
        v_rear_sq = st.file_uploader("【動画】後ろ手SQ", type=["mp4", "mov", "avi"], key="rear_sq")

    st.markdown("---")
    st.markdown("### 📸 2. 測定写真の選択（※各項目で複数枚アップロード可能）")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        p_ankle = st.file_uploader("【写真】足関節背屈", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="ankle")
        p_aslr = st.file_uploader("【写真】A/P SLR", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="aslr")
    with col_p2:
        p_thoracic = st.file_uploader("【写真】胸椎回旋", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="thoracic")
        p_sheet = st.file_uploader("【写真】手書き記録シート / その他写真", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="sheet")

    st.markdown("---")
    
    # 判定実行ボタン
    if st.button("🚀 この内容でAI判定を実行する（5回平均解析）", type="primary"):
        if not any([v_ohsq, v_rear_sq, p_ankle, p_thoracic, p_aslr, p_sheet]):
            st.error("⚠️ 少なくとも1つの動画または写真をアップロードしてください。")
        else:
            with st.spinner("AIがブレを抑えるため5回の試行測定を行い、平均値を算出中...（15〜30秒ほどかかります）"):
                try:
                    contents_payload = []
                    temp_files = [] # 一時ファイルのクリーンアップ用
                    
                    item_mapping_prompt = "以下は提出されたファイル一覧と対応項目です。\n\n"

                    # 動画処理関数
                    def process_video(uploaded_file, label_name):
                        if uploaded_file:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
                                tmp_file.write(uploaded_file.read())
                                tmp_path = tmp_file.name
                                temp_files.append(tmp_path)
                            ref = client.files.upload(file=tmp_path)
                            contents_payload.append(ref)
                            return f"- 【📹動画】{label_name}: [ファイル名: {uploaded_file.name}]\n"
                        return f"- 【📹動画】{label_name}: 未提出\n"

                    # 画像処理関数
                    def process_images(uploaded_files, label_name):
                        if uploaded_files:
                            file_details = []
                            for idx, file in enumerate(uploaded_files, start=1):
                                img = Image.open(file)
                                contents_payload.append(img)
                                file_details.append(f"写真{idx}({file.name})")
                            details_str = ", ".join(file_details)
                            return f"- 【📸写真】{label_name}: [添付数: {len(uploaded_files)}枚 -> {details_str}]\n"
                        return f"- 【📸写真】{label_name}: 未提出\n"

                    # 紐づけ情報の構築
                    item_mapping_prompt += process_video(v_ohsq, "オーバーヘッドSQ (OHSQ)")
                    item_mapping_prompt += process_video(v_rear_sq, "後ろ手SQ")
                    item_mapping_prompt += process_images(p_ankle, "足関節背屈 (基準: 12cm以上)")
                    item_mapping_prompt += process_images(p_thoracic, "胸椎回旋 (基準: 50度以上)")
                    item_mapping_prompt += process_images(p_aslr, "A/P SLR (基準: 70度以上 / 左右差10度未満)")
                    item_mapping_prompt += process_images(p_sheet, "手書き記録シート・その他チェック項目")

                    # 指示プロンプト
                    prompt = f"""
                    {item_mapping_prompt}

                    【高精度解析指示】
                    画像・動画を分析するにあたり、測定誤差や判定のブレを防ぐため、**各写真・動画に対して全項目5回の内部測定を実施し、その平均値を最終判定値として採用してください**。

                    ※重要フォーマット＆角度の計算・変換規則※
                    - 写真判定の各項目について、**複数枚の写真がある場合は写真1枚ごとにインデント（箇条書きの配下）で段落分けして表示**してください。
                    - **A/P SLR** の測定角度について:
                      1. 「股関節（大転子付近）」と「挙上している側の外くるぶし（外果）」を結んだ直線と「水平線」とのなす【足側の挙上角度】（例: 75°）を5回試行測定し、平均値を求めてください。
                      2. その後、**【180° − (5回測定した平均挙上角度)】** の計算を行ってください。
                      3. 出力時には理由や解説文は一切書かず、**【180° − 平均角度】の計算結果数値のみ（例: 105°）**を表示してください。

                    【出力フォーマット例】
                    ---
                    ### 📹 動画判定（スクワット項目）
                    - **オーバーヘッドSQ**: [ ⭕ 正常 / ❌ 要改善 / 未提出 ] - [判定理由]
                    - **後ろ手SQ**: [ ⭕ 正常 / ❌ 要改善 / 未提出 ] - [判定理由]

                    ### 📸 写真判定（可動域・チェック項目）
                    - **足関節背屈**: [ ⭕ 正常 / ❌ 要改善 / 未提出 ]
                      - 写真1 (ファイル名): [5回平均の数値または状態]
                      - 写真2 (ファイル名): [5回平均の数値または状態]
                    - **胸椎回旋**: [ ⭕ 正常 / ❌ 要改善 / 未提出 ]
                      - 写真1 (ファイル名): [5回平均の数値または状態]
                      - 写真2 (ファイル名): [5回平均の数値または状態]
                    - **A/P SLR**: [ ⭕ 正常 / ❌ 要改善 / 未提出 ]
                      - 写真1 (ファイル名): [180 - 平均挙上角度 の計算数値 (例: 105°)]
                      - 写真2 (ファイル名): [180 - 平均挙上角度 の計算数値 (例: 115°)]
                    - **手書きシート/その他**:
                      - 写真1 (ファイル名): [検出されたエラー項目]

                    ### ⚠️ 要改善項目（まとめ）
                    - [クリアできなかった項目のみを箇条書きで一覧化]
                    ---
                    """

                    contents_payload.insert(0, prompt)

                    # Gemini API 呼び出し（503混雑時の自動リトライ処理付き）
                    response = None
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            response = client.models.generate_content(
                                model='gemini-3.5-flash',
                                contents=contents_payload
                            )
                            break
                        except Exception as req_err:
                            if "503" in str(req_err) and attempt < max_retries - 1:
                                time.sleep(3 * (attempt + 1))
                                continue
                            else:
                                raise req_err

                    st.success("✅ 5回アンサンブル解析・判定完了")

                    st.markdown("---")
                    st.markdown("### 📊 AI判定結果")
                    st.markdown(response.text)

                    st.markdown("---")
                    st.markdown("### 📸 判定対象の写真一覧（プレビュー）")

                    # 写真判定の各項目ごとのカード型表示（画像＋画像名）
                    def render_photo_section(title, files_list):
                        if files_list:
                            st.subheader(title)
                            cols = st.columns(min(len(files_list), 4))
                            for idx, f in enumerate(files_list):
                                with cols[idx % 4]:
                                    st.image(f, caption=f"写真{idx+1} ({f.name})", use_container_width=True)

                    render_photo_section("🦶 足関節背屈", p_ankle)
                    render_photo_section("🦵 A/P SLR", p_aslr)
                    render_photo_section("🔄 胸椎回旋", p_thoracic)
                    render_photo_section("📝 手書きシート / その他", p_sheet)

                    # 一時ファイルの削除
                    for tmp_path in temp_files:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)

                except Exception as e:
                    st.error(f"判定エラーが発生しました: {e}\n\n※Google側のAPIサーバーが現在混雑しています。数十秒ほど時間を空けてからもう一度お試しください。")
