# POST /v1/vlm/analyze

Analyze an image and get a description or answer a question about it.

## Overview

This endpoint sends an image (and an optional text prompt) to the Vision and Language Model (VLM). The VLM processes the image and returns a textual response. This can be used for image captioning, object detection, or answering visual questions.

## Request

### Method

`POST`

### URL

`/v1/vlm/analyze`

### Headers

- `Authorization`: `Bearer <Your-Auth-Token>` (Optional)
- `Content-Type`: `application/json`

### Body

A JSON object containing the image data and prompt.

```json
{
    "image": "base64_encoded_image_string_or_url",
    "prompt": "Describe this image"
}
```

- `image` (string, required): Image data as base64-encoded string or URL.
- `prompt` (string, optional): Text prompt for image analysis. Defaults to "Describe this image".

## Response

### Success (200 OK)

Returns a JSON object containing the VLM's analysis.

```json
{
    "description": "The image shows a golden retriever playing fetch in a sunny park."
}
```

### Error

- **422 Unprocessable Entity**: If the `image` field is missing.
- **401 Unauthorized**: If the authorization token is missing or invalid.
- **500 Internal Server Error**: If the VLM service fails to process the image.

## Example

### cURL

```bash
curl -X POST "http://127.0.0.1:5500/v1/vlm/analyze" \
-H "Content-Type: application/json" \
-d '{
    "image": "https://example.com/image.jpg",
    "prompt": "What color is the dog?"
}'
```

### JavaScript (Fetch API)

```javascript
const imageUrl = "https://example.com/image.jpg";
const prompt = "What is the main subject of this image?";

fetch('http://127.0.0.1:5500/v1/vlm/analyze', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        image: imageUrl,
        prompt: prompt
    }),
})
.then(response => response.json())
.then(data => console.log(data.description))
.catch(error => console.error('Error:', error));
```
