import argparse
from icalendar import Calendar
from requests import get, post
from copy import deepcopy
from datetime import datetime, date, timedelta


def get_calendar(url):
	data = get(url)
	cal = Calendar.from_ical(data.text)
	return cal

def send_slack_msg(msg):
	post(args.callback_url, json={
		'method': 'post',
		'contentType': 'json',
		'payload': msg
	})

def date_to_str(d):
	today = date.today()

	if d == today:
		return 'Today'
	elif d == (today - timedelta(days=1)):
		return 'Yesterday'
	elif d == (today + timedelta(days=1)):
		return 'Tomorrow'
	else:
		return d.strftime('%d.%m.%Y')

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Notify slack on ical events')
	parser.add_argument('-c', '--calendar', type=str, required=True)
	parser.add_argument('-d', '--callback_url', type=str, required=True)
	parser.add_argument('-p', '--period', choices=['today', 'week'], default='today')
	parser.add_argument('-n', '--names', nargs='*', type=str)
	parser.add_argument('-g', '--channel', type=str)
	parser.add_argument('-u', '--username', type=str, default='Calendar bot')
	args = parser.parse_args()

	period_text = 'today' if args.period == 'today' else 'this week'

	now = datetime.now()
	period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

	if args.period == 'week' and period_start.weekday() != 0:
		period_start = period_start - timedelta(days=period_start.weekday())

	period_end = period_start + timedelta(days=1)

	if args.period == 'week':
		period_end = period_end + timedelta(days=6)

	period_start = period_start.date()
	period_end = period_end.date()

	print('Checking events from %s to %s' % (period_start, period_end))

	slack_msg = {
		'channel': args.channel,
		'username': args.username,
		'icon_emoji': ':date:',
		'text': '%s events' % period_text,
		'attachments': [],
	}

	calendar = get_calendar(args.calendar)

	for component in calendar.walk():
		if component.name == 'VEVENT':
			if args.names:
				matched = False
				for name in args.names:
					if component['SUMMARY'].startswith(name):
						matched = True
						break

				if not matched:
					continue

			intersects = component['DTSTART'].dt >= period_start and component['DTSTART'].dt < period_end

			if not intersects and component.get('DTEND'):
				intersects = (component['DTSTART'].dt <= period_start and component['DTEND'].dt > period_start + timedelta(days=1)) \
							or (component['DTSTART'].dt < period_end and component['DTEND'].dt >= period_end)

			if not intersects:
				continue

			fields = []

			if component.get('DTEND') and component['DTSTART'].dt != component['DTEND'].dt - timedelta(days=1):
				fields.append({
					'title': 'From',
					'value': date_to_str(component['DTSTART'].dt),
					'short': True
				})
				fields.append({
					'title': 'To',
					'value': date_to_str(component['DTEND'].dt - timedelta(days=1)),
					'short': True
				})
			elif args.period != 'today':
				fields.append({
					'title': 'Date',
					'value': date_to_str(component['DTSTART'].dt),
					'short': True
				})

			fields.append({
				'title': 'Description',
				'value': component['DESCRIPTION']
			})

			slack_msg['attachments'].append({
				'fields': fields,
				'text': component['SUMMARY'],
			})
		elif component.name == 'VCALENDAR':
			slack_msg['text'] = '%s on %s' % (component['X-WR-CALNAME'], period_text)
		else:
			print(component)

	if len(slack_msg['attachments']):
		send_slack_msg(slack_msg)
