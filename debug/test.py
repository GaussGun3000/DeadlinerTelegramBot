

'''ts = datetime.now()
ts2 = datetime.strptime('2021-09-30-18-30', '%Y-%m-%d-%H-%M')
delta = ts2-ts
print(f'{delta.days} {round(delta.seconds / 3600, 1)}')'''
'''text = str(input())
text += f' {datetime.now().year}'
date = datetime.strptime(text, '%d.%m %H:%M %Y').timestamp()
print(date)'''


"""def current_time():  # returns UTC +3 datetime object
    return datetime.now(pytz.timezone('Europe/Moscow')).replace(tzinfo=None)


def convert_date(date: float):  # converts timestamp object to normal russian date format
    return datetime.fromtimestamp(date).strftime('%d.%m %H:%M')


def text(dls):
    text = f'Сейчас {current_time().strftime("%d.%m %H:%M")}\n' + f'{config.messages["deadlines"]}\n'
    for dl in dls:
        text += f' - По предмету {dl.subject} задача {dl.task} до {convert_date(dl.date)}'
        if (datetime.fromtimestamp(dl.date) - current_time()).days < 1:  # if less than a day left put warning sign
            text += '\u26A0\n'
        else:
            text += '\n'
    return text


deadlines = database.load()
deadlines.append(database.Deadline(subject='new', task='some task', date=datetime.strptime('6.10 19:00 2021', '%d.%m %H:%M %Y').timestamp()))
deadlines.sort()
print(text(deadlines))"""


'''
MSC = datetime.now(pytz.timezone('Europe/Moscow'))
print(MSC.strftime('%d.%m %H:%M'))'''
