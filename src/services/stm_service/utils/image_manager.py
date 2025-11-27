import base64
import re
import uuid
from pathlib import Path


class LocalImageManager:
    def __init__(self, base_dir: str = "static/images"):
        # 프로젝트 루트 기준 static/images 폴더 생성
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_base64_image(self, base64_string: str, user_id: str) -> str:
        """
        Base64 문자열을 이미지 파일로 저장하고 URL 경로를 반환합니다.
        Returns: "/static/images/{user_id}/{uuid}.png"
        """
        # 1. 헤더 제거 (data:image/png;base64,...) 및 확장자 추출
        if "," in base64_string:
            header, encoded = base64_string.split(",", 1)
            # 확장자 추출 (간단한 정규식)
            ext_match = re.search(r"data:image/(\w+);base64", header)
            extension = ext_match.group(1) if ext_match else "png"
        else:
            encoded = base64_string
            extension = "png"

        # 2. 사용자별 디렉토리 생성
        user_dir = self.base_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        # 3. 파일명 생성 및 저장
        filename = f"{uuid.uuid4()}.{extension}"
        file_path = user_dir / filename

        try:
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(encoded))

            # 4. URL 경로 반환 (FastAPI StaticFiles에서 mount한 경로 기준)
            return f"/static/images/{user_id}/{filename}"

        except Exception as e:
            print(f"Failed to save image: {e}")
            return None

    def process_images(self, messages: list[dict], user_id: str) -> list[dict]:
        """메시지 내의 Base64를 로컬 파일 URL로 변환"""
        processed = []
        for msg in messages:
            # Make a copy to avoid modifying the original
            msg_copy = msg.copy()

            # 1. 메시지 내용이 리스트인지 확인 (멀티모달)
            # Messages are dicts with 'content' key, not objects
            content = msg_copy.get("content")
            if isinstance(content, list):
                new_content = []
                for item in content:
                    # Make a copy of the item
                    item_copy = item.copy() if isinstance(item, dict) else item

                    # 2. 이미지 타입이고 url이 base64인 경우 감지
                    if (
                        isinstance(item_copy, dict)
                        and item_copy.get("type") == "image_url"
                    ):
                        url_data = item_copy.get("image_url", {}).get("url", "")

                        if url_data.startswith("data:image"):
                            # 파일로 저장
                            saved_path = self.save_base64_image(url_data, user_id)
                            if saved_path:
                                # Base64 대신 파일 경로(URL)로 교체
                                if isinstance(item_copy.get("image_url"), dict):
                                    item_copy["image_url"] = item_copy[
                                        "image_url"
                                    ].copy()
                                    item_copy["image_url"]["url"] = saved_path

                    new_content.append(item_copy)
                msg_copy["content"] = new_content
            processed.append(msg_copy)
        return processed
