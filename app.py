import streamlit as st
from PIL import Image
from google import genai
import os
import tempfile

st.set_page_config(page_title="フィジカル・スクリーニング AI判定", layout="wide")
st.title("🏃 フィジカル・スクリーニング AI判定ツール")
st.caption("項目ごとに複数枚の写真・動画を選択して判定します。")

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
    if st.button("🚀 この内容でAI判定を実行する", type="primary"):
        if not any([v_ohsq, v_rear_sq, p_ankle, p_thoracic, p_aslr, p_sheet]):
            st.error("⚠️ 少なくとも1つの動画または写真をアップロードしてください。")
        else:
            with st.spinner("AIが指定された項目別に解析中..."):
                try:
                    contents_payload = []
                    temp_files = [] # 一時ファイルのクリーンアップ用
                    
                    item_mapping_prompt = "以下は提出されたファイル一覧と対応項目です。\n\n"

                    # 動画処理関数（ファイル名を記録）
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

                    # 画像処理関数（写真番号とファイル名を記録）
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

                    【解析指示】
                    上記の対応関係に基づいて画像を解析し、スクリーニングの良否判定のみを行ってください。
                    どのファイル（写真1, 写真2, または動画ファイル名など）に基づいて判定したかを各判定項目の横に必ず明記してください。
                    アドバイスや雑感は不要です。未提出の項目がある場合は「未提出」と表記してください。

                    【出力フォーマット】
                    ---
                    ### 📹 動画判定（スクワット項目）
                    - **オーバーヘッドSQ**: [ ⭕ 正常 / ❌ 要改善 / 未提出 ] - (対象: [動画ファイル名]) [理由]
                    - **後ろ手SQ**: [ ⭕ 正常 / ❌ 要改善 / 未提出 ] - (対象: [動画ファイル名]) [理由]

                    ### 📸 写真判定（可動域・チェック項目）
                    - **足関節背屈**: [ ⭕ 正常 / ❌ 要改善 / 未提出 ] - (対象: [写真1(ファイル名) 等]) [数値または状態]
                    - **胸椎回旋**: [ ⭕ 正常 / ❌ 要改善 / 未提出 ] - (対象: [写真1(ファイル名) 等]) [数値または状態]
                    - **A/P SLR**: [ ⭕ 正常 / ❌ 要改善 / 未提出 ] - (対象: [写真1(ファイル名) 等]) [数値または状態]
                    - **手書きシート/その他**: (対象: [写真1(ファイル名) 等]) [検出されたエラー項目]

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

                    # 一時ファイルの削除
                    for tmp_path in temp_files:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)

                except Exception as e:
                    st.error(f"判定エラーが発生しました: {e}")
