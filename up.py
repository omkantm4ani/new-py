from flask import Flask, request, jsonify
import os
from werkzeug.utils import secure_filename
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

# YouTube API scopes
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = "token.json"

# Folder to temporarily store uploaded files
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_authenticated_service():
    """Authenticate with YouTube API and return the service."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

@app.route("/upload", methods=["GET"])
def upload_form():
    return '''
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="video"><br>
        <input type="text" name="title" placeholder="Video Title"><br>
        <textarea name="description" placeholder="Video Description"></textarea><br>
        <select name="privacy">
            <option value="public">Public</option>
            <option value="unlisted">Unlisted</option>
            <option value="private">Private</option>
        </select><br>
        <button type="submit">Upload</button>
    </form>
    '''

@app.route("/upload", methods=["POST"])
def upload_video():
    if "video" not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    video = request.files["video"]
    title = request.form.get("title", "Untitled Video")
    description = request.form.get("description", "")
    privacy = request.form.get("privacy", "public")  # Options: public, unlisted, private

    # Secure filename and save
    filename = secure_filename(video.filename)
    filepath = os.path.join(UPLOAD_FOLDER, f"temp_{filename}")
    video.save(filepath)

    try:
        youtube = get_authenticated_service()

        # YouTube video metadata
        body = {
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": privacy}
        }

        # Use correct MIME type (e.g., "video/mp4")
        media = MediaFileUpload(filepath, resumable=True, mimetype="video/mp4")

        # Upload video
        request_upload = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = request_upload.execute()

        video_id = response.get("id")
        video_url = f"https://youtu.be/{video_id}"
        return jsonify({"message": "Upload successful", "video_url": video_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        # Clean up the uploaded temp file
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Error deleting temp file: {e}")

# ✅ This block is now Heroku-compatible
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
