
# from django.core.mail import send_mail
# from django.conf import settings
from .models import TicketEmailTemplate



from django.core.mail import EmailMultiAlternatives
from django.conf import settings

# def send_task_email(event, task, recipient):
#     try:
#         print(f"[EMAIL DEBUG] Triggered event: {event}")

#         template = TicketEmailTemplate.objects.filter(
#             email_event=event,
#             is_active='Y'
#         ).first()

#         if not template:
#             print(f"[EMAIL ERROR] No template found for event: {event}")
#             return

#         if not recipient or not recipient.email:
#             print("[EMAIL ERROR] No recipient email")
#             return

#         print(f"[EMAIL DEBUG] Sending to: {recipient.email}")

#         # ✅ SAFER CONTEXT (avoid None values)
#         context = {
#             "task_id": task.id,
#             "task_name": task.task.name if task.task else "",
#             "user": getattr(task.user, "firstname", "") or getattr(task.user, "username", ""),
#             "status": task.status.name if task.status else "",
#             "approver": getattr(recipient, "firstname", "") or getattr(recipient, "username", ""),
#         }

#         # ✅ Format HTML
#         html_content = template.email_template.format(**context)

#         # ✅ Plain text fallback (important)
#         text_content = f"""
#         Task: {context['task_name']}
#         Submitted By: {context['user']}
#         Status: {context['status']}
#         """

#         email = EmailMultiAlternatives(
#             subject=f"Task Update - {event}",
#             body=text_content,
#             from_email=settings.DEFAULT_FROM_EMAIL,
#             to=[recipient.email],
#         )

#         # ✅ Attach HTML
#         email.attach_alternative(html_content, "text/html")

#         email.send()

#         print(f"[EMAIL SUCCESS] Mail sent successfully to {recipient.email}")

#     except Exception as e:
#         print("[EMAIL EXCEPTION]", str(e))


def send_task_email(event, task, recipient):
    try:
        print(f"[EMAIL DEBUG] Triggered event: {event}")

        template = TicketEmailTemplate.objects.filter(
            email_event=event,
            is_active='Y'
        ).first()

        if not template:
            print(f"[EMAIL ERROR] No template found for event: {event}")
            return False  # return False if email not sent

        if not recipient or not recipient.email:
            print("[EMAIL ERROR] No recipient email")
            return False

        print(f"[EMAIL DEBUG] Sending to: {recipient.email}")

        context = {
            "task_id": task.id,
            "task_name": task.task.name if task.task else "",
            "user": getattr(task.user, "firstname", "") or getattr(task.user, "username", ""),
            "status": task.status.name if task.status else "",
            "approver": getattr(recipient, "firstname", "") or getattr(recipient, "username", ""),
        }

        html_content = template.email_template.format(**context)
        text_content = f"Task: {context['task_name']}\nSubmitted By: {context['user']}\nStatus: {context['status']}"

        email = EmailMultiAlternatives(
            subject=f"Task Update - {event}",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        print(f"[EMAIL SUCCESS] Mail sent successfully to {recipient.email}")
        return True

    except Exception as e:
        print("[EMAIL EXCEPTION]", str(e))
        return False

# def send_task_email(event, task, recipient):
#     try:
#         print(f"[EMAIL DEBUG] Triggered event: {event}")

#         template = TicketEmailTemplate.objects.filter(
#             email_event=event,
#             is_active='Y'
#         ).first()

#         if not template:
#             print(f"[EMAIL ERROR] No template found for event: {event}")
#             return

#         if not recipient or not recipient.email:
#             print("[EMAIL ERROR] No recipient email")
#             return

#         print(f"[EMAIL DEBUG] Sending to: {recipient.email}")

#         message = template.email_template.format(
#             task_id=task.id,
#             task_name=task.task.name if task.task else "",
#             user=task.user.firstname,
#             status=task.status.name if task.status else "",
#             approver=recipient.firstname 
#         )

#         response = send_mail(
#             subject=f"Task Update - {event}",
#             message=message,
#             from_email=settings.DEFAULT_FROM_EMAIL,
#             recipient_list=[recipient.email],
#             fail_silently=False   # ❗ IMPORTANT
#         )

#         # ✅ Django returns number of emails sent
#         if response == 1:
#             print(f"[EMAIL SUCCESS] Mail sent successfully to {recipient.email}")
#         else:
#             print(f"[EMAIL FAILED] Mail not sent. Response: {response}")

#     except Exception as e:
#         print("[EMAIL EXCEPTION]", str(e))

# def send_task_email(event, task, recipient):
#     try:
#         template = TicketEmailTemplate.objects.filter(
#             email_event=event,
#             is_active='Y'
#         ).first()

#         if not template:
#             print(f"[EMAIL] No template found for event: {event}")
#             return

#         # Replace placeholders
#         message = template.email_template.format(
#             task_id=task.id,
#             task_name=task.task.name if task.task else "",
#             user=task.user.username,
#             status=task.status.name if task.status else "",
#             approver=recipient.username
#         )

#         send_mail(
#             subject=f"Task Update - {event}",
#             message=message,
#             from_email=settings.DEFAULT_FROM_EMAIL,
#             recipient_list=[recipient.email],
#             fail_silently=True
#         )

#         print(f"[EMAIL SENT] {event} → {recipient.email}")

#     except Exception as e:
#         print("[EMAIL ERROR]", str(e))



