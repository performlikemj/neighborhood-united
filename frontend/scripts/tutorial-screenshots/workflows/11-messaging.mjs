/**
 * Workflow 11 - Messaging
 *
 * Captures the messaging workflow between a customer and chef,
 * including sending a message from the customer side and
 * receiving / replying from the chef side.
 */

export const meta = { name: 'Messaging', dir: '11_messaging' }

export default async function capture(ctx) {
  const { chefPage, customerPage, baseUrl, screenshot, openChefTab, settle } = ctx

  // ── Customer Side: Navigate to chef and open chat ──

  // 1. Navigate customer to My Chefs page and find ferris
  let chatOpened = false

  try {
    await customerPage.goto(`${baseUrl}/my-chefs`)
    await customerPage.waitForLoadState('networkidle')
    await settle(customerPage, 800)

    // Look for ferris in the My Chefs list
    const ferrisLink = customerPage.getByText(/ferris/i).first()
    if (await ferrisLink.count()) {
      await screenshot(customerPage, 'customer-my-chefs-page')

      // Click on ferris to open the Chef Hub
      await ferrisLink.click()
      await customerPage.waitForLoadState('networkidle')
      await settle(customerPage, 800)
      await screenshot(customerPage, 'customer-chef-hub')

      // 2. Click "Message Chef" button
      const messageBtn = customerPage.getByRole('button', { name: /Message Chef/i })
      if (await messageBtn.count()) {
        await messageBtn.click()
        await settle(customerPage, 800)

        // Wait for chat input to appear
        await customerPage.locator('textarea.chat-input').waitFor({ timeout: 10000 })
        chatOpened = true
      }
    }
  } catch {
    // My Chefs route did not work; try the public chef directory as fallback
  }

  // Fallback: try navigating directly to the chefs directory to find ferris
  if (!chatOpened) {
    try {
      await customerPage.goto(`${baseUrl}/chefs`)
      await customerPage.waitForLoadState('networkidle')
      await settle(customerPage, 600)

      const searchInput = customerPage.locator('input.search-input')
      if (await searchInput.count()) {
        await searchInput.fill('ferris')
        await settle(customerPage, 600)
      }

      const ferrisResult = customerPage.getByText('ferris', { exact: false }).first()
      if (await ferrisResult.count()) {
        await ferrisResult.click()
        await customerPage.waitForLoadState('networkidle')
        await settle(customerPage, 600)
      }

      await screenshot(customerPage, 'customer-chef-profile')

      // Try to find a message button on the public profile or chef hub
      const messageBtnFallback = customerPage.getByRole('button', { name: /Message Chef/i })
      if (await messageBtnFallback.count()) {
        await messageBtnFallback.click()
        await settle(customerPage, 800)
        await customerPage.locator('textarea.chat-input').waitFor({ timeout: 10000 })
        chatOpened = true
      }
    } catch {
      // Could not open chat via fallback either
    }
  }

  if (chatOpened) {
    // 3. Type a message and screenshot before sending
    const chatInput = customerPage.locator('textarea.chat-input')
    await chatInput.fill(
      "Hi Chef! I'm interested in your weekly meal prep service for my family of 4."
    )
    await settle(customerPage, 400)
    await screenshot(customerPage, 'customer-chat-typed-message')

    // 4. Click send and screenshot the sent message
    const sendBtn = customerPage.locator('.chat-send-btn')
    await sendBtn.click()
    await settle(customerPage, 1000)
    await screenshot(customerPage, 'customer-chat-message-sent')

    // 5. Close the chat panel on customer side
    const closeBtn = customerPage.locator('.chat-panel-close')
    if (await closeBtn.count()) {
      await closeBtn.click()
      await customerPage.locator('.chat-panel').waitFor({ state: 'detached', timeout: 10000 }).catch(() => {})
      await settle(customerPage, 400)
    }
  } else {
    // If chat could not be opened, screenshot whatever state we are in
    await screenshot(customerPage, 'customer-messaging-unavailable')
  }

  // ── Chef Side: View conversations and reply ──

  // 6. Navigate chef to Messages tab
  await openChefTab(chefPage, 'Messages')
  await settle(chefPage, 800)

  // 7. Screenshot the conversations list (may show unread indicator)
  await screenshot(chefPage, 'chef-conversations-list')

  // 8. Click the first conversation to open it
  const conversations = chefPage.locator('.conversation-item')
  if (await conversations.count()) {
    await conversations.first().click()
    await settle(chefPage, 800)

    // Wait for the chat input to appear
    try {
      await chefPage.locator('textarea.chat-input').waitFor({ timeout: 10000 })
    } catch {
      // Chat input may not appear if there is no active conversation
    }
    await screenshot(chefPage, 'chef-conversation-opened')

    // 9. Type a reply message
    const chefChatInput = chefPage.locator('textarea.chat-input')
    if (await chefChatInput.count()) {
      await chefChatInput.fill(
        "Welcome! I'd love to help your family. Let me put together a customized meal plan based on your preferences. Do you have any dietary restrictions?"
      )
      await settle(chefPage, 400)
      await screenshot(chefPage, 'chef-reply-typed')

      // 10. Send the reply and screenshot the conversation with both messages
      const chefSendBtn = chefPage.locator('.chat-send-btn')
      await chefSendBtn.click()
      await settle(chefPage, 1000)
      await screenshot(chefPage, 'chef-reply-sent')
    }

    // 11. Close the chat panel on chef side
    const chefCloseBtn = chefPage.locator('.chat-panel-close')
    if (await chefCloseBtn.count()) {
      await chefCloseBtn.click()
      await chefPage.locator('.chat-panel').waitFor({ state: 'detached', timeout: 10000 }).catch(() => {})
      await settle(chefPage, 400)
    }
  } else {
    await screenshot(chefPage, 'chef-no-conversations')
  }
}
