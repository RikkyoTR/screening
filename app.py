import streamlit as st
from PIL import Image
from google import genai
import os
import tempfile

# ページ基本設定
st.set_page_config(page_title="フィジカル・スクリーニング AI判定", layout="wide")
st.title("🏃 フィジカル・スクリーニング 簡易AI判定ツール")
st.caption("動画（OHSQ・後ろ手SQ）と 写真（その他全項目）を選択して一括判定します。")

# APIキーの設定
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.warning("⚠️ Streamlit Secrets に 'GEMINI_API_KEY' を設定してください。")
    api_key = st.text_input("Gemini API Key を入力:", type="password")

if api_key:
    client = genai.Client(api_key=api_key)

    # メディアのアップロードエリア
    uploaded_files = st.file_uploader(
        "判定する写真（可動域・シート等）と 動画（OHSQ・後ろ手SQ）をすべて選択してください",
        type=["jpg", "jpeg", "png", "mp4", "mov", "avi"],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.write(f"📁 選択中のファイル: {len(uploaded_files)} 件")
        
        # プレビュー表示
        cols = st.columns(min(len(uploaded_files), 4))
        for idx, file in enumerate(uploaded_files):
            with cols[idx % 4]:
                if file.type.startswith("image"):
                    st.image(Image.open(file), caption=f"📸 {file.name}", use_container_width=True)
                elif file.type.startswith("video"):
                    st.video(file)
                    st.caption(f"📹 {file.name}")

        st.markdown("---")
        
        # 判定実行ボタン
        if st.button("🚀 AI判定を実行する", type="primary"):
            with st.spinner("AIが映像・画像を解析中..."):
                try:
                    contents_payload = []
                    temp_files = [] # 一時ファイルのクリーンアップ用

                    # ファイルのロード処理
                    for file in uploaded_files:
                        if file.type.startswith("image"):
                            img = Image.open(file)
                            contents_payload.append(img)
                        
                        elif file.type.startswith("video"):
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
                                tmp_file.write(file.read())
                                tmp_file_path = tmp_file.name
                                temp_files.append(tmp_file_path)

                            # Files API 経由で動画を送信
                            video_file_ref = client.files.upload(file=tmp_file_path)
                            contents_payload.append(video_file_ref)

                    # 判定ロジック専用プロンプト（アドバイスは出力しない）
                    prompt = """
                    添付された【写真】および【動画】を解析し、スクリーニング結果の良否判定のみを行ってください。アドバイスや解説などの文章は一切不要です。

                    【判定ルールと役割分担】

                    1. **📹 動画で判定する項目（動作・フォーム解析）**
                       - **オーバーヘッドSQ (OHSQ)**:
                         * 上体がスネと平行を保てているか？
                         * 大腿が水平ラインより下がっているか？
                         * バーが足の上に保持できているか？
                       - **後ろ手SQ**:
                         * 動作のブレ、下降時の不自然な動き、可動域制限の有無

                    2. **📸 写真で判定する項目（静止姿勢・シート解析）**
                       - **足関節背屈**: 壁との距離（12cm未満は要改善）
                       - **胸椎回旋**: 角度（50°未満は要改善）
                       - **A/P SLR**: 角度（70°未満）および 左右差（10°以上は要改善）
                       - **その他（立位体前屈/後屈、ヒップフレクサー、Yバランスなど）**: エラーの有無
                       - ※記録用紙の写真が含まれる場合は、数値を直接読み取って判定してください。

                    【出力フォーマット】
                    ---
                    ### 📹 動画判定（スクワット項目）
                    - **オーバーヘッドSQ**: [ ⭕ 正常 / ❌ 要改善 ] - [詳細・理由]
                    - **後ろ手SQ**: [ ⭕ 正常 / ❌ 要改善 ] - [詳細・理由]

                    ### 📸 写真判定（可動域・チェック項目）
                    - **足関節背屈**: [ ⭕ 正常 / ❌ 要改善 ] - [数値または状態]
                    - **胸椎回旋**: [ ⭕ 正常 / ❌ 要改善 ] - [数値または状態]
                    - **A/P SLR**: [ ⭕ 正常 / ❌ 要改善 ] - [数値または状態]
                    - **その他検出項目**: [エラーがある項目のみ箇条書き]

                    ### ⚠️ 要改善項目（まとめ）
                    - [クリアできなかった項目のみを箇条書きで一覧化]
                    ---
                    """
                    
                    contents_payload.insert(0, prompt)

                    # Gemini API 呼び出し
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=contents_payload
                    )

                    st.success("✅ 判定完了")
                    st.markdown(response.text)

                    # 後処理（アップロード動画の削除）
                    for tmp_path in temp_files:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)

                except Exception as e:
                    st.error(f"判定エラーが発生しました: {e}")
