import re

fr = open("PORTFOLIO.md", "r")
line_cnt = 1
coin_table = {}
for line in fr:
    if line_cnt > 2:
        # Match only English strings
        english_strings = re.findall(r'[a-zA-Z]+', line)
        coin_table[english_strings[0]] = True
    line_cnt += 1
fr.close()
coins = list(coin_table.keys())
coins = sorted(coins, reverse=False)
print(len(coins))
for coin in coins:
    print(coin)
