이 봇은 yt_dlp로 유튜브 같은 사이트에서 영상/음악 URL을 추출하거나 다운로드할 때 쓰는 파이썬 라이브러리로 만든 디스코드 음악 봇입니다

다음과 같은 pip 설치 패키지가 필요합니다

pip install discord.py

pip install yt-dlp

pip install asyncio

pip install PyNaCl

pip install yt-dlp

pip install ffmpeg-python


별도로 시스템에 FFmpeg가 설치되어 있어야 합니다:
윈도우 사용자라면, https://www.gyan.dev/ffmpeg/builds/ 에서 최신 zip 파일 다운로드 후,
bin/ffmpeg.exe가 PATH에 잡히게끔 환경변수 설정을 해야 합니다.

YOUR_DISCORD_BOT_TOKEN 자리에는 본인의 디스코드 봇 토큰이 있어야 합니다.
