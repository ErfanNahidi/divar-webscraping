#!/bin/bash

# از کاربر تعداد دفعات اجرا را دریافت می‌کنیم
read -p "Enter the number of times you want to run scraping.py: " count

# حلقه برای اجرای مکرر فایل
for ((i=1; i<=count; i++))
do
  echo "Running scraping.py (Run #$i)"
  python3 scraping.py
  
  # بررسی اینکه اسکریپت با موفقیت اجرا شده یا نه
  if [ $? -ne 0 ]; then
    echo "Error occurred during execution. Exiting..."
    exit 1
  fi
  
  echo "Finished run #$i"
done

echo "All runs completed."
