@echo off
REM Daily exit-reminder job: notifies IT, HR and the manager 7 days before an
REM employee's last working day. Scheduled via Windows Task Scheduler.
cd /d "C:\Users\Hari Keerthi\Desktop\Projects\OffBoarding\backend"
set "DJANGO_SETTINGS_MODULE=config.settings.development"
"C:\Users\Hari Keerthi\AppData\Local\Programs\Python\Python311\python.exe" manage.py send_exit_reminders >> "C:\Users\Hari Keerthi\Desktop\Projects\OffBoarding\backend\exit_reminders.log" 2>&1
