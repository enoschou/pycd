# install FFmpeg manually
# pip install pydub
# pip install google-cloud-aiplatform google-cloud-speech google-cloud-texttospeech google-cllud-firestore


import os
from random import choices

from pydub import AudioSegment
from google.cloud import speech, texttospeech, firestore
from vertexai.preview.generative_models import GenerativeModel, Content, Part


class GcpChat:

    def __init__(self, collection, instruction=None, service=None):
        if service:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = service
        self.users = self._init_firestore(collection)
        self.instruction = instruction

    def _init_firestore(self, collection):
        try:
            client = firestore.Client()
            return client.collection(collection)
        except Exception as e:
            print(e)

    def _stt(self, content):
        # init
        speech_client = speech.SpeechClient()

        # setting
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=44100,
            audio_channel_count=2,
            language_code="zh-TW",
            max_alternatives=1
        )

        # transcript
        response = speech_client.recognize(config=config, audio=audio)
        if response and response.results:
            return response.results[0].alternatives[0].transcript
        return None

    def chat(self, userid, content, format='mp3'):
        if format != 'mp3':
            content = self.to_mp3(content)
            if not content:
                return f'bad {format}'

        text = self._stt(content)
        if not text:
            return 'bad stt'

        text = self._chat(userid, text)
        if not text:
            return 'bad chat'
        
        content = self._tts(text)
        if not content:
            return 'bad tts'

        return content, self._get_duration(content)

    def _stt(self, content):
        # init
        speech_client = speech.SpeechClient()

        # setting
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=44100,
            audio_channel_count=2,
            language_code="zh-TW",
            max_alternatives=1
        )

        # transcript
        response = speech_client.recognize(config=config, audio=audio)
        if response and response.results:
            return response.results[0].alternatives[0].transcript
        return None

    def _chat(self, userid, text):
        history = self._read_history(userid)
        r, h = self._gemini(text, instruction=self.instruction, history=history)
        self._save_history(userid, h)
        return r

    def _read_history(self, userid):
        u = self.users.document(userid).get().to_dict()
        if u and (hs := u.get('history')):
            return [Content(role=('user', 'model')[i%2], parts=[Part.from_text(h)]) for i, h in enumerate(hs)]

    def _save_history(self, userid, history):
        u = {'history': [h.text for h in history]}
        if self.users.document(userid).get().exists:
            self.users.document(userid).update(u)
        else:
            self.users.add(document_data=u, document_id=userid)

    def _gemini(self, text, instruction=None, history=None):
        model = GenerativeModel('gemini-1.5-pro-001',
                                system_instruction=[instruction] if instruction else None)
        chat = model.start_chat(history=history)

        generation_config = {
            "max_output_tokens": 512,
            "temperature": 1.5,
            "top_p": 1,
            "top_k": 40
        }

        response = chat.send_message(text, generation_config=generation_config)
        return response.text, chat.history

    def _tts(self, text):
        # init
        client = texttospeech.TextToSpeechClient()

        # setting
        input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code='cmn-TW',
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

        # synthesize
        response = client.synthesize_speech(input=input, voice=voice, audio_config=audio_config)
        return response.audio_content

    @classmethod
    def to_mp3(cls, content, format='m4a'):
        if format in ['m4a', 'wav']:
            filename = ''.join(choices('0123456789', k=10))+'.'+format
            with open(filename, 'wb') as f:
                f.write(content)
            try:
                audio = AudioSegment.from_file(filename, format=format)
                mp3 = ''.join(choices('0123456789', k=8))+'.mp3'
                audio.export(mp3)
                os.remove(filename)
                with open(mp3, 'rb') as f:
                    content = f.read()
                os.remove(mp3)
                return content
            except Exception as e:
                print(e)

    def _get_duration(self, content, format='mp3'):
        if format in ['mp3', 'm4a', 'wav']:
            filename = ''.join(choices('0123456789', k=10))+'.'+format
            with open(filename, 'wb') as f:
                f.write(content)
            try:
                audio = AudioSegment.from_file(filename, format=format)
                duration = len(audio) / 1000.
                os.remove(filename)
                return duration
            except Exception as e:
                print(e)
        return 0
