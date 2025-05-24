import random
import time

fortunes = [
    "A syntax error in time saves nine.",
    "Beware of the segfault in your heart.",
    "Today is a good day to refactor your life.",
    "He who commits without pushing is lost.",
    "Love is like recursion – beautiful but dangerous if unchecked.",
    "You will meet someone special... in your Git history.",
    "Try again after a full system reboot (including emotions).",
    "The compiler of fate has no backspace key.",
    "Embrace the bugs — they make you human.",
    "Your destiny has been deprecated."
]

print("🥠 Cracking your Pythonic fortune cookie...\n")
time.sleep(2)

fortune = random.choice(fortunes)
print(f"✨ Your fortune: \"{fortune}\" ✨")
