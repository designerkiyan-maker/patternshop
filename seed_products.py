"""Add 10 sample products — run once after first deploy."""
import sqlite3, os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_database.db")
conn = sqlite3.connect(DB)
c = conn.cursor()

# Ensure categories exist
c.execute("SELECT COUNT(*) FROM categories")
if c.fetchone()[0] == 0:
    default_cats = ["الگوهای زنانه", "مانتو و пальто", "بلوز و شومیز", "لباس مجلسی", "ملزومات"]
    for n in default_cats:
        c.execute("INSERT INTO categories (name) VALUES (?)", (n,))
    conn.commit()
    print("Created default categories.")

cats = c.execute("SELECT id FROM categories ORDER BY id LIMIT 5").fetchall()
cat_ids = [r[0] for r in cats]

samples = [
    (cat_ids[0 % len(cat_ids)], "مانتو کلاسیک بلند", 45000, "الگوی مانتوی بلند کلاسیک سایز 38-48. شامل جلو، پشت و آستین. پارچه: کرپ، جیر."),
    (cat_ids[1 % len(cat_ids)], "شلوار پارچه‌ای گشاد", 35000, "الگوی شلوار ورددار سایز 36-50. مناسب مجلس و روزمره. پارچه: کرپ ماهوت."),
    (cat_ids[2 % len(cat_ids)], "بلوز آستین کوتاه مجلسی", 28000, "الگوی بلوز مجلسی یقه هفت سایز 38-46. پارچه: حریر، گیپور."),
    (cat_ids[3 % len(cat_ids)], "پیراهن ساحلی بلند", 32000, "الگوی پیراهن ساحلی بلند تا زانو سایز 36-48. پارچه: نخ، ویسکوز."),
    (cat_ids[4 % len(cat_ids)], "لباس شب بلند ساده", 55000, "الگوی لباس شب بلند با دامن کلوش سایز 38-46. پارچه: ساتن، تافته."),
    (cat_ids[0 % len(cat_ids)], "کت تک زنانه", 48000, "الگوی کت تک با یقه انگلیسی سایز 38-50. پارچه: کرپ، لینن."),
    (cat_ids[1 % len(cat_ids)], "شومیز یقه اسکی", 25000, "الگوی شومیز راحت یقه اسکی آستین بلند سایز 36-46. پارچه: نمدی، ویسکوز."),
    (cat_ids[2 % len(cat_ids)], "چادر نماز طرح‌دار", 22000, "الگوی چادر نماز با طرح گل‌دار سایز آزاد. پارچه: کرپ، پلی‌استر."),
    (cat_ids[3 % len(cat_ids)], "کیف پارچه‌ای دستی", 18000, "الگوی کیف پارچه‌ای دست‌دوز ۳۰×۲۵ سانتی‌متر با جیب داخلی. پارچه: کتان."),
    (cat_ids[4 % len(cat_ids)], "روبالشی تزئینی", 15000, "الگوی روبالشی مربع ۴۰×۴۰ با حاشیه تزئینی. پارچه: مخمل، کتان."),
]

print(f"Inserting {len(samples)} sample products into {DB} ...")
for cat_id, name, price, desc in samples:
    c.execute("INSERT INTO products (category_id, name, price, description) VALUES (?, ?, ?, ?)",
              (cat_id, name, price, desc))
    print(f"  ✅ {name} — {price:,} تومان")

conn.commit()
conn.close()
print("Done.")
