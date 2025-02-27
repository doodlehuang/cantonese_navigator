import re
import asyncio
import openai
from gtts import gTTS
from io import BytesIO
from pydub import AudioSegment
import pyaudio
from playwright.async_api import async_playwright

# 输入你的API密钥

api_key = 'your_api_key'
base_url = 'your_api_base_url'

client = openai.AsyncClient(api_key=api_key, base_url=base_url)

# 音频配置
CHUNK_SIZE = 1024
SILENCE_DURATION = 100  # 0.1秒静音缓冲

async def text_generator(text: str):
    """流式文本生成器"""
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "你係一個粵語助手，需要用粵語口語講解以下內容，請只輸出口語文本，唔好用任何格式化文本。"},
            {"role": "user", "content": text}
        ],
        stream=True,
        max_tokens=500
    )
    
    buffer = ""
    async for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            print(content, end='', flush=True)
            buffer += content
            
            # 分句逻辑
            if re.search(r'[。！？\n]', content):
                sentences = re.split(r'(?<=[。！？\n])', buffer)
                for sentence in sentences[:-1]:  # 保留最后未完成部分
                    if sentence.strip():
                        yield sentence.strip()
                buffer = sentences[-1]
    
    if buffer.strip():
        yield buffer.strip()

async def play_audio(text: str):
    """异步播放音频"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, sync_play_audio, text)

def sync_play_audio(text: str):
    """同步音频处理"""
    # 生成静音缓冲
    silence = AudioSegment.silent(duration=SILENCE_DURATION)
    
    # 生成TTS
    tts = gTTS(text, lang='yue')
    mp3_io = BytesIO()
    tts.write_to_fp(mp3_io)
    mp3_io.seek(0)
    
    # 合并静音和语音
    audio = silence + AudioSegment.from_mp3(mp3_io)
    
    # 初始化音频系统
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=audio.channels,
        rate=audio.frame_rate,
        output=True
    )
    
    # 播放音频
    stream.write(audio.raw_data)
    
    # 清理资源
    stream.stop_stream()
    stream.close()
    p.terminate()

async def handle_page_load(page):
    """处理页面加载"""
    print(f"\n页面加载完成: {page.url}")
    try:
        await page.wait_for_load_state("networkidle")
        
        # 提取页面内容
        body_text = await page.evaluate("""
            () => {
                const main = document.querySelector('main') || 
                          document.querySelector('article') || 
                          document.body;
                return main.innerText;
            }
        """)
        
        # 截断文本
        truncated_text = body_text[:8192] + ("..." if len(body_text) > 8192 else "")
        print("\n开始生成粤语摘要:")
        
        # 流式处理和播放
        async for sentence in text_generator(truncated_text):
            await play_audio(sentence)
        
        print("\n\n摘要完成")
        
    except Exception as e:
        print(f"处理出错: {str(e)}")

async def main():
    """主函数"""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--mute-audio"]
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        page.on("load", lambda: asyncio.create_task(handle_page_load(page)))
        
        await page.goto("https://www.gov.uk/british-national-overseas-bno-visa")
        print("浏览器已启动，可以自由浏览...")
        
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())