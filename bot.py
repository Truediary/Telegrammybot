import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, CallbackContext,
    ConversationHandler, MessageHandler, filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(
    SELECTING_ACTION, ADDING_PRODUCT_NAME, ADDING_PRODUCT_QUANTITY,
    ADDING_PRODUCT_PHOTO, DELETING_PRODUCT, SELECTING_PRODUCT,
    SELECTING_QUANTITY, CONFIRM_ORDER
) = range(8)

# База данных
products = {}
orders = []
admin_ids = [7101920091]  # Замените на ваш ID

async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update.message:
        await update.message.reply_text('🚨 Произошла ошибка. Пожалуйста, попробуйте снова.')

def main_menu_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    if is_admin:
        keyboard = [
            [InlineKeyboardButton("➕ Добавить товар", callback_data='add_product')],
            [InlineKeyboardButton("🗑️ Удалить товар", callback_data='delete_product')],
            [InlineKeyboardButton("📦 Список товаров", callback_data='view_products_admin')],
            [InlineKeyboardButton("📋 Список заказов", callback_data='view_orders')]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🛍️ Купить товар", callback_data='buy_product')],
            [InlineKeyboardButton("📦 Наши товары", callback_data='view_products')]
        ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    is_admin = user_id in admin_ids
    
    text = (
        "👋 Добро пожаловать в *Магазинчик Чудес*!\n\n"
        "Здесь вы можете приобрести уникальные товары по выгодным ценам!"
    )
    
    await update.message.reply_photo(
        photo='https://pngimg.com/image/84642',  # Замените на реальную ссылку
        caption=text,
        reply_markup=main_menu_keyboard(is_admin),
        parse_mode='Markdown'
    )

async def add_product_start(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_caption(
        caption="📝 Введите название нового товара:",
        reply_markup=None
    )
    return ADDING_PRODUCT_NAME

async def add_product_name(update: Update, context: CallbackContext) -> int:
    context.user_data['new_product'] = {'name': update.message.text.strip()}
    await update.message.reply_text("🔢 Введите количество товара:")
    return ADDING_PRODUCT_QUANTITY

async def add_product_quantity(update: Update, context: CallbackContext) -> int:
    try:
        quantity = int(update.message.text)
        if quantity <= 0:
            raise ValueError
        context.user_data['new_product']['quantity'] = quantity
        await update.message.reply_text("📸 Пришлите фото товара:")
        return ADDING_PRODUCT_PHOTO
    except ValueError:
        await update.message.reply_text("❌ Некорректное количество! Введите целое число больше 0:")
        return ADDING_PRODUCT_QUANTITY

async def add_product_photo(update: Update, context: CallbackContext) -> int:
    photo = update.message.photo[-1].file_id
    product = context.user_data['new_product']
    product['photo'] = photo
    product_id = max(products.keys(), default=0) + 1
    products[product_id] = product
    
    await update.message.reply_photo(
        photo=photo,
        caption=f"✅ Товар успешно добавлен!\n\n"
               f"*Название:* {product['name']}\n"
               f"*Количество:* {product['quantity']}",
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard(True)
    )
    return ConversationHandler.END

async def view_products(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    if not products:
        await query.edit_message_caption(caption="😔 В настоящее время товаров нет в наличии.")
        return
    
    media_group = []
    for idx, (product_id, product) in enumerate(products.items()):
        caption = (
            f"🛍 *{product['name']}*\n"
            f"📦 Остаток: {product['quantity']} шт.\n"
            f"🆔 ID: {product_id}"
        )
        media = InputMediaPhoto(
            media=product.get('photo', 'https://example.com/default.jpg'),
            caption=caption if idx == 0 else '',
            parse_mode='Markdown'
        )
        media_group.append(media)
    
    await context.bot.send_media_group(chat_id=query.message.chat_id, media=media_group)
    await query.message.delete()

async def view_orders(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    if not orders:
        await query.edit_message_caption(caption="📭 Список заказов пуст.")
        return
    
    text = "📋 *Список заказов:*\n\n"
    for order in orders:
        text += (
            f"🆔 Заказ #{order['order_id']}\n"
            f"📦 Товар: {order['product_name']}\n"
            f"🔢 Количество: {order['quantity']} шт.\n"
            f"👤 Пользователь: @{order['user_id']}\n"
            f"────────────────────\n"
        )
    
    await query.edit_message_caption(
        caption=text,
        parse_mode='Markdown'
    )

async def buy_product_start(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    if not products:
        await query.edit_message_caption(caption="😔 В настоящее время товаров нет в наличии.")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton(
            f"{product['name']} ({product['quantity']} шт.)", 
            callback_data=f'select_{product_id}'
        )]
        for product_id, product in products.items()
    ]
    await query.edit_message_caption(
        caption="🎁 Выберите товар для покупки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_PRODUCT

async def select_product(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    product_id = int(query.data.split('_')[1])
    product = products.get(product_id)
    
    if not product or product['quantity'] <= 0:
        await query.answer("❌ Этот товар больше недоступен!", show_alert=True)
        return ConversationHandler.END
    
    context.user_data['selected_product'] = product_id
    await query.edit_message_caption(
        caption=f"🔢 Введите количество для товара *{product['name']}*\n"
               f"Доступно: {product['quantity']} шт.",
        reply_markup=None,
        parse_mode='Markdown'
    )
    return SELECTING_QUANTITY

async def confirm_quantity(update: Update, context: CallbackContext) -> int:
    try:
        quantity = int(update.message.text)
        product_id = context.user_data.get('selected_product')
        product = products.get(product_id)
        
        if not product or quantity <= 0 or quantity > product['quantity']:
            raise ValueError
            
        context.user_data['quantity'] = quantity
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить заказ", callback_data='confirm_order')],
            [InlineKeyboardButton("❌ Отменить", callback_data='cancel_order')]
        ]
        
        await update.message.reply_photo(
            photo=product.get('photo', 'https://pngimg.com/image/84642'),
            caption=f"🛒 *Подтверждение заказа*\n\n"
                   f"📦 Товар: {product['name']}\n"
                   f"🔢 Количество: {quantity} шт.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return CONFIRM_ORDER
        
    except ValueError:
        await update.message.reply_text("❌ Некорректное количество! Введите целое число:")
        return SELECTING_QUANTITY

async def complete_order(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    product_id = context.user_data['selected_product']
    quantity = context.user_data['quantity']
    product = products[product_id]
    
    # Обновляем количество
    products[product_id]['quantity'] -= quantity
    
    # Создаем заказ
    order = {
        'order_id': len(orders) + 1,
        'product_id': product_id,
        'product_name': product['name'],
        'quantity': quantity,
        'user_id': update.effective_user.username
    }
    orders.append(order)
    
    # Уведомление администратора
    for admin_id in admin_ids:
        await context.bot.send_message(
            admin_id,
            f"🚨 *Новый заказ #{order['order_id']}*\n"
            f"📦 Товар: {product['name']}\n"
            f"🔢 Количество: {quantity}\n"
            f"👤 Пользователь: @{update.effective_user.username}",
            parse_mode='Markdown'
        )
    
    await query.edit_message_caption(
        caption="🎉 Заказ успешно оформлен!\n"
               "Администратор свяжется с вами в ближайшее время.",
        reply_markup=None
    )
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("❌ Действие отменено.")
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token("8053836586:AAF0UdoMzHY55nlEh4_XOmq6FaCW0YFvIWg").build()
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Обработчик для администраторов
    admin_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_product_start, pattern='^add_product$')],
        states={
            ADDING_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)],
            ADDING_PRODUCT_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_quantity)],
            ADDING_PRODUCT_PHOTO: [MessageHandler(filters.PHOTO, add_product_photo)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )

    # Обработчик для покупок
    buy_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_product_start, pattern='^buy_product$')],
        states={
            SELECTING_PRODUCT: [CallbackQueryHandler(select_product, pattern='^select_')],
            SELECTING_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_quantity)],
            CONFIRM_ORDER: [CallbackQueryHandler(complete_order, pattern='^confirm_order$')]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(admin_conversation)
    application.add_handler(buy_conversation)
    application.add_handler(CallbackQueryHandler(view_products, pattern='^view_products$'))
    application.add_handler(CallbackQueryHandler(view_products, pattern='^view_products_admin$'))
    application.add_handler(CallbackQueryHandler(view_orders, pattern='^view_orders$'))
    application.add_handler(CallbackQueryHandler(cancel, pattern='^cancel_order$'))

    application.run_polling()

if __name__ == '__main__':
    main()
