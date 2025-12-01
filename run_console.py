import asyncio
import os
import sys

# Add current directory to path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import AutoViralBot
from src.console_ui import Console

async def main():
    # Initialize Console
    Console.print_panel("AutoViral Bot - CLI Mode", title="METRATRON", style="bold green")
    
    try:
        Console.log_step("Initializing Bot Systems...")
        bot = AutoViralBot()
    except Exception as e:
        Console.log_error(f"Failed to initialize bot: {e}")
        return

    while True:
        print("\n")
        Console.print_separator()
        topic = input("Enter video topic (or 'q' to quit): ").strip()
        if topic.lower() == 'q':
            break
            
        if not topic:
            continue

        style = input("Enter style (HORROR, MOTIVACION, CURIOSIDADES, etc.) [Default: CURIOSIDADES]: ").strip() or "CURIOSIDADES"
        
        Console.log_step(f"Starting generation for topic: {topic}")
        
        try:
            # Run generation
            result = await bot.generate_video(
                topic=topic,
                style=style,
                duration_minutes=1.0,
                voice="es-MX-DaliaNeural", # Default voice
                use_subtitles=True
            )
            
            if result and result.get("status") == "success":
                Console.log_success(f"Video generated successfully!")
                Console.log_info(f"Path: {result.get('video_path')}")
            else:
                Console.log_error("Generation finished but status was not success.")
                
        except Exception as e:
            Console.log_error(f"Generation failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
