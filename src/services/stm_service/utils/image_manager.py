"""
TODO: Image storage feature for STM service.

This module is currently disabled because:
1. The current project focus is on real-time screen recognition, not image history.
2. Storing images in chat history increases DB size and token consumption unnecessarily.
3. The architecture needs improvement for better extensibility across different backends.

Future improvements needed before enabling:
- Add abstract methods to STMService base class for consistency
- Get base_url from main config file instead of STM config (avoid duplication)
- Implement selective image loading to reduce traffic and context window usage

To re-enable this feature:
1. Uncomment the LocalImageManager class below
2. Add image_manager back to STMService base class
3. Update MongoDBSTM to use process_images and resolve_image_urls
4. Add base_url configuration to main settings
"""

# import base64
# import re
# import uuid
# from pathlib import Path


# class LocalImageManager:
#     def __init__(self, base_dir: str = "static/images"):
#         # 프로젝트 루트 기준 static/images 폴더 생성
#         self.base_dir = Path(base_dir)
#         self.base_dir.mkdir(parents=True, exist_ok=True)

#     def save_base64_image(self, base64_string: str, user_id: str) -> str:
#         """
#         Base64 문자열을 이미지 파일로 저장하고 URL 경로를 반환합니다.
#         Returns: "/v1/static/images/{user_id}/{uuid}.png"
#         """
#         # 1. 헤더 제거 (data:image/png;base64,...) 및 확장자 추출
#         if "," in base64_string:
#             header, encoded = base64_string.split(",", 1)
#             # 확장자 추출 (간단한 정규식)
#             ext_match = re.search(r"data:image/(\w+);base64", header)
#             extension = ext_match.group(1) if ext_match else "png"
#         else:
#             encoded = base64_string
#             extension = "png"

#         # 2. 사용자별 디렉토리 생성
#         user_dir = self.base_dir / user_id
#         user_dir.mkdir(parents=True, exist_ok=True)

#         # 3. 파일명 생성 및 저장
#         filename = f"{uuid.uuid4()}.{extension}"
#         file_path = user_dir / filename

#         try:
#             with open(file_path, "wb") as f:
#                 f.write(base64.b64decode(encoded))

#             # 4. URL 경로 반환 (FastAPI StaticFiles에서 mount한 경로 기준)
#             return f"/v1/static/images/{user_id}/{filename}"

#         except Exception as e:
#             print(f"Failed to save image: {e}")
#             return None

#     def process_images(self, messages: list[dict], user_id: str) -> list[dict]:
#         """메시지 내의 Base64를 로컬 파일 URL로 변환"""
#         processed = []
#         for msg in messages:
#             # Make a copy to avoid modifying the original
#             msg_copy = msg.copy()

#             # 1. 메시지 내용이 리스트인지 확인 (멀티모달)
#             # Messages are dicts with 'content' key, not objects
#             content = msg_copy.get("content")
#             if isinstance(content, list):
#                 new_content = []
#                 for item in content:
#                     # Make a copy of the item
#                     item_copy = item.copy() if isinstance(item, dict) else item

#                     # 2. 이미지 타입이고 url이 base64인 경우 감지
#                     if (
#                         isinstance(item_copy, dict)
#                         and item_copy.get("type") == "image_url"
#                     ):
#                         url_data = item_copy.get("image_url", {}).get("url", "")

#                         if url_data.startswith("data:image"):
#                             # 파일로 저장
#                             saved_path = self.save_base64_image(url_data, user_id)
#                             if saved_path:
#                                 # Base64 대신 파일 경로(URL)로 교체
#                                 if isinstance(item_copy.get("image_url"), dict):
#                                     item_copy["image_url"] = item_copy[
#                                         "image_url"
#                                     ].copy()
#                                     item_copy["image_url"]["url"] = saved_path

#                     new_content.append(item_copy)
#                 msg_copy["content"] = new_content
#             processed.append(msg_copy)
#         return processed

#     def resolve_image_urls(self, messages: list[dict], base_url: str) -> list[dict]:
#         """
#         조회 시 상대경로를 절대 URL로 변환합니다.

#         Args:
#             messages: OpenAI 형식의 메시지 리스트
#             base_url: 서버 기본 URL (예: "http://127.0.0.1:8000")

#         Returns:
#             list[dict]: 절대 URL로 변환된 메시지 리스트
#         """
#         resolved = []
#         for msg in messages:
#             msg_copy = msg.copy()
#             content = msg_copy.get("content")

#             if isinstance(content, list):
#                 new_content = []
#                 for item in content:
#                     item_copy = item.copy() if isinstance(item, dict) else item

#                     if (
#                         isinstance(item_copy, dict)
#                         and item_copy.get("type") == "image_url"
#                     ):
#                         url = item_copy.get("image_url", {}).get("url", "")
#                         # 상대경로인 경우 base_url을 붙여서 절대 URL로 변환
#                         if url.startswith("/v1/static"):
#                             if isinstance(item_copy.get("image_url"), dict):
#                                 item_copy["image_url"] = item_copy["image_url"].copy()
#                                 item_copy["image_url"]["url"] = f"{base_url}{url}"

#                     new_content.append(item_copy)
#                 msg_copy["content"] = new_content
#             resolved.append(msg_copy)
#         return resolved

#     def get_file_path_from_url(self, url: str) -> Path | None:
#         """
#         URL에서 실제 파일 경로를 추출합니다.

#         Args:
#             url: 이미지 URL (예: "/v1/static/images/user/uuid.jpeg")

#         Returns:
#             Path | None: 실제 파일 경로 또는 None
#         """
#         if not url.startswith("/v1/static/images/"):
#             return None

#         # "/v1/static/images/user/uuid.jpeg" -> "user/uuid.jpeg"
#         relative_path = url.replace("/v1/static/images/", "")
#         return self.base_dir / relative_path

#     def delete_image(self, url: str) -> bool:
#         """
#         URL에 해당하는 이미지 파일을 삭제합니다.

#         Args:
#             url: 이미지 URL

#         Returns:
#             bool: 삭제 성공 여부
#         """
#         file_path = self.get_file_path_from_url(url)
#         if file_path and file_path.exists():
#             try:
#                 file_path.unlink()
#                 return True
#             except Exception:
#                 return False
#         return False
