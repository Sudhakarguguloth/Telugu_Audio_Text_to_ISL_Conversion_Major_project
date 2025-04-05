from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.staticfiles import finders
from django.contrib.auth.decorators import login_required
from indicnlp.tokenize import indic_tokenize
from indicnlp.normalize import indic_normalize
from google.cloud import speech_v1p1beta1 as speech
import io
import os
import re
from pydub import AudioSegment
from googletrans import Translator

translator = Translator()

# Telugu to English mapping for common words


FILTER_WORDS = {"the"}  # Words to filter out from translations

# Home page
def home_view(request):
    return render(request, 'home.html')

# About page
def about_view(request):
    return render(request, 'about.html')

# Contact page
def contact_view(request):
    return render(request, 'contact.html')

# Animation (main translation + ISL rendering) view
@login_required(login_url="login")
def animation_view(request):
    if request.method == 'POST':
        if 'audio' in request.FILES:
            audio_file = request.FILES['audio']
            text = recognize_telugu_speech(audio_file)
        else:
            text = request.POST.get('sen')
            category = request.POST.get('category')

        if category != 'Telugu':
            return render(request, 'animation.html', {'error': 'Please select Telugu'})

        expression_result = evaluate_expression(text)
        if expression_result:
            filtered_words = check_results(expression_result)
            return render(request, 'animation.html', {'words': filtered_words,'text': f"{text}", 'tel_words': expression_result})

        words = preprocess_text(text)
        processed_words = translate_words(words)
        filtered_words = check_animations(processed_words)

        return render(request, 'animation.html', {'words': filtered_words, 'text': text, 'tel_words': words})
    else:
        return render(request, 'animation.html')

# 🔹 Telugu preprocessing (normalize + clean + tokenize)
def preprocess_text(text):
    """Normalize, clean, and tokenize Telugu text."""
    normalizer = indic_normalize.IndicNormalizerFactory().get_normalizer('te')
    
    # Normalize text
    text = normalizer.normalize(text)
    
    # Remove non-Telugu characters and clean up
    text = re.sub(r"[^\u0C00-\u0C7F\s]", "", text)
    
    # Normalize spacing
    text = re.sub(r"\s+", " ", text).strip()
    
    # Tokenize
    words = list(indic_tokenize.trivial_tokenize(text, lang='te'))
    
    return words

# 🔹 Translation of each Telugu word to English
def translate_words(words):
    """Translate Telugu words to English using a predefined dictionary or fallback to translator."""
    processed_words = []

    for w in words:
        

        if True:
            try:
                # Use Google Translate if not in dictionary
                translation = translator.translate(w, src='te', dest='en').text.lower()
                mapped_word = re.sub(r"[^\w\s]", "", translation)  # Clean punctuation
            except Exception:
                mapped_word = w  # Fallback to original word
        
        # Split and filter
        processed_words.extend([word.strip() for word in mapped_word.split() if word and word not in FILTER_WORDS])

    return processed_words

# 🔹 Check for available GIFs or fallback to letters
def check_animations(processed_words):
    filtered_words = []
    for word in processed_words:
        path = f"{word}.mp4"
        if finders.find(path):
            filtered_words.append(word)
        else:
            # Fallback to character-level representation
            filtered_words.extend(list(word))
    return filtered_words

def check_results(processed_words):
    filtered_words = []
    for word in processed_words:
        # Directly split number strings into digits
        filtered_words.extend(list(word))
    return filtered_words

# 🔹 Calculator expression evaluation (if input is like 2+2)
def evaluate_expression(text):
    try:
        expression = re.sub(r'[^0-9+\-*/().]', '', text)
        if any(op in expression for op in ['+', '-', '*', '/']):
            return str(eval(expression))
        return None
    except Exception as e:
        return f"Error evaluating expression: {e}"

# 🔹 Google Cloud speech recognition (Telugu)
def recognize_telugu_speech(audio_file):
    try:
        client = speech.SpeechClient()
        audio = AudioSegment.from_file(audio_file)
        audio.export("temp.wav", format="wav")
        with io.open("temp.wav", "rb") as audio_content:
            content = audio_content.read()
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="te-IN"
        )
        response = client.recognize(config=config, audio=audio)
        for result in response.results:
            return result.alternatives[0].transcript
        return "Speech recognition failed"
    except Exception as e:
        return f"Error processing audio: {e}"

# Signup view
def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})

# Login view
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect(request.POST.get('next', 'animation'))
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

# Logout
def logout_view(request):
    logout(request)
    return redirect("home")
