TOKEN = ''
# constant strings:
messages = {
    'start': 'Welcоme! Это бот по контролю дедлайнов группы 0307. Доступ к функциям имеют только подтвержденные админом'
             ' @Gauss_Gun пользователи. Чтобы отправить заявку, перешлите админу результат на команды /get_my_id. '
             '\nИстекшие дедлайны очищаются ночью (в рестарт сервера)\n',
    'deadlines': 'Текущий список дедлайнов: \n',
    'commands': 'Список команд: \n/show_all - показать все дедлайны\n/subscribe - подписка на напоминания\n'
                '/unsub - отписаться от уведомлений\n/add - добавить дедлайн\n/mark_done - отметить выполненным'
                '\n/delete - удалить последний добавленный.',
    'help': '\n\nДобавление дедлайнов доступно только подтверждённым пользователям. Чтобы добавить, следуйте инструкциям'
            ' бота по команде /add. Задания рекомендуется описывать коротко. Не добавляйте два одинаковых задания! Если '
            'требуется поменять время, можно попросить отредактировать время у одного из админов. (@Gauss_Gun, @Maks7uh,'
            ' @Enfort, @westerndert). Уведомления о дедлайнах приходят за 7, 3 и 1 суток до истечения срока задания '
            'подписанным пользователям. По команде /mark_done можно отметить для себя задания выполненными, чтобы по ним'
            ' не приходили уведомления, а при запросе всего списка у отмеченных заданий стояла галочка.',
    'admin_help': 'Админские команды:\n /announce - объявление\n/edit - изменение времени дедлайна\n/delete - '
                  'удалить любой.',
    'nothing_left': 'Ура! Тут ничего не осталось. Как говорится, зачёт есть, можно и поесть.',
    'input_subj': 'Введите название предмета',
    'input_task': 'Назовите задание',
    'input_date': 'Введите дату и время дедлайна в формате дд.мм ЧЧ:ММ (Пример: 30.09 18:50)',
    'successful_add': 'Дедлайн успешно добавлен!',
    'deleted': 'Успешно удалено.',
    'delete_last': 'Удалить последний добавленный дедлайн?',
    'no_recent_add': 'Вы не добавляли дедлайнов после последнего рестарта',
    'cancel': 'Окей, отмена',
    'no_deadlines': 'Дедлайнов нет.',
    'already_subbed': 'Вы уже подписаны.',
    'already_unsubbed': 'Вы уже отписаны.',
    'subscribed': 'Вы подписались на уведомления!',
    'unsubscribed': 'Вы отписались от уведомлений!',
    'choose_mark': 'Что отмечаем сделанным?',
    'marked': ' отмечено выполненным! Чтобы снять отметку, повторите действие над дедлайном.',
    'unmarked': 'отметка снята с',
    'not_subbed': 'Эта функция работает только для пользователей, подписанных на уведомления!',
    'choose_task': 'Выберите дедлайн для удаления',
    'not_verified': 'Вы не являетесь подтвержденным пользователем. Пройти подтверждение можно через админа @Gauss_Gun',
    'wrong_format': 'Неверный формат даты. Попробуйте ещё раз.',
    'wrong_date': 'Указана прошедшая дата. Прошлого не вернуть! Попробуйте ввести ещё раз',
    'wrong_input': 'Принимается текст (буквы/цифры). Не нужно пытаться прислать стикер/картинку. Попробуйте ещё раз.',
    'oops': 'Что-то не так с введёнными данными. Возможно, стоит открыть клавитару telegram под полем ввода',
    'on_text': 'Я не люблю попусту болтать. Используйте команды! Узнать список можно через /help',
    'announce': 'Введите текст уведомления',
    'len_limit': 'Предельная длина сообщения - 4000 символов. Попробуйте что-нибудь покороче!',
    'choose_edit': 'Выберите редактируемый дедлайн',
    'date_edited': 'Новая дата сохранена.',
    'choose_property': 'Что редактируем?'
}
# verification process is manual for safety. Just add needed id to this list to give user add right (and redeploy)
VERIFIED_USERS = [405810751, 340185927, 1161517629, 474776926, 464209002, 924557178, 455180878, 122874751, 510901162
                  , 777456537, 1222636987, 1258491135, 451098228, 357512400, 479882064, 716382198, 727712544,
                  1383023738, 272573291, 329352234, 296437275]
ADMINS = [405810751, 474776926, 924557178, 340185927]
PERIOD = 180  # time between periodic tasks in sec
