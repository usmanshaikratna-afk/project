@echo off
echo Starting Driver Safety System...
echo.
echo Checking for shape predictor file...
if not exist "models\shape_predictor_68_face_landmarks.dat" (
    echo Downloading shape predictor file...
    powershell -Command "Invoke-WebRequest -Uri 'http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2' -OutFile 'models\shape_predictor_68_face_landmarks.dat.bz2'"
    echo Extracting...
    powershell -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.Bzip2]::Decompress('models\shape_predictor_68_face_landmarks.dat.bz2', 'models\shape_predictor_68_face_landmarks.dat')"
    del models\shape_predictor_68_face_landmarks.dat.bz2
    echo Done!
) else (
    echo Shape predictor file found.
)
echo.
echo Installing requirements...
pip install -r requirements.txt
echo.
echo Starting application...
python app.py
pause