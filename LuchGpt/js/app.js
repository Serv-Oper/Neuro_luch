document.addEventListener('DOMContentLoaded', () => {
  let isLoggedIn = false;
  let isGuestMode = false;
  let guestRequestsCount = 0;
  const GUEST_REQUEST_LIMIT = 3;
  let attachedFilesData = [];
  let userRegisteredEmail = '';
  const MAX_ATTACHMENTS = 5;
  let authToken = localStorage.getItem('authToken');
  let guestAuthToken = null;
  let currentChatId = null;
  let userChats = [];

  const API_BASE_URL = 'https://b91b-2a09-bac5-48a1-505-00-80-183.ngrok-free.app';
  const GOOGLE_CLIENT_ID = '258066409140-suhq9anknken0t1mj8hs23fecgisvdgv.apps.googleusercontent.com';

  const appLayout = document.getElementById('appLayout');
  const sidebar = document.getElementById('sidebar');
  const authLinkSidebarFooter = document.getElementById('authLinkSidebarFooter');
  const logoutLinkSidebar = document.getElementById('logoutLinkSidebar');
  const requiresAuthElements = document.querySelectorAll('.requires-auth');
  const chatArea = document.querySelector('.chat-area');
  const welcomeMessage = document.querySelector('.welcome-message');
  const chatTitleHeader = document.getElementById('chatTitleHeader');
  const authLinkMainHeader = document.getElementById('authLinkMainHeader');
  const attachFileBtn = document.getElementById('attachFileBtn');
  const fileAttachmentInput = document.getElementById('fileAttachmentInput');
  const attachmentPreviewContainer = document.getElementById('attachmentPreviewContainer');
  const actionButtons = document.querySelectorAll('.action-buttons .btn');
  const chatTextArea = document.querySelector('.input-area textarea');
  const sendButton = document.querySelector('.icon-btn.btn-send');

  const sidebarToggleBtnLocal = document.getElementById('sidebarToggleBtnLocal');
  const sidebarOpenBtnGlobal = document.getElementById('sidebarOpenBtnGlobal');
  const toggleImage = sidebarToggleBtnLocal ? sidebarToggleBtnLocal.querySelector('.icon img') : null;

  const chatListUl = document.querySelector('.chat-history-section .chat-list');
  const btnNewChat = document.querySelector('.btn-new-chat');

  const profileUsernameSpan = document.getElementById('sidebarUsername');
  const subscriptionStatusSpan = document.getElementById('subscriptionStatus');
  const subscriptionExpiresSpan = document.getElementById('subscriptionExpires');
  const usageFastSpan = document.getElementById('usageFast');
  const usageSmartSpan = document.getElementById('usageSmart');
  const usageImageSpan = document.getElementById('usageImage');
  const loginOverlay = document.getElementById('loginOverlay');
  const loginForm = document.getElementById('loginForm');
  const loginEmailInput = document.getElementById('loginEmail');
  const loginPasswordInput = document.getElementById('loginPassword');
  const switchToRegisterLink = document.getElementById('switchToRegisterLink');
  const forgotPasswordLink = document.getElementById('forgotPasswordLink');
  const googleLoginButtons = document.querySelectorAll('.btn-google-login-trigger');
  const registerOverlay = document.getElementById('registerOverlay');
  const registerForm = document.getElementById('registerForm');
  const registerEmailInput = document.getElementById('registerEmail');
  const registerPasswordInput = document.getElementById('registerPassword');
  const registerConfirmPasswordInput = document.getElementById('registerConfirmPassword');
  const registerErrorMessage = document.getElementById('registerErrorMessage');
  const registerErrorText = document.getElementById('registerErrorText');
  const closeRegisterErrorBtn = document.getElementById('closeRegisterErrorBtn');
  const switchToLoginLinkFromRegister = document.getElementById('switchToLoginLinkFromRegister');
  const verifyEmailOverlay = document.getElementById('verifyEmailOverlay');
  const verifyCodeForm = document.getElementById('verifyCodeForm');
  const codeInputs = document.querySelectorAll('.code-input');
  const verificationEmailDisplay = document.getElementById('verificationEmailDisplay');
  const verifyErrorMessage = document.getElementById('verifyErrorMessage');
  const verifyErrorText = document.getElementById('verifyErrorText');
  const closeVerifyErrorBtn = document.getElementById('closeVerifyErrorBtn');
  const resendCodeLink = document.getElementById('resendCodeLink');
  const backToLoginFromVerifyLink = document.getElementById('backToLoginFromVerifyLink');
  const forgotPasswordOverlay = document.getElementById('forgotPasswordOverlay');
  const forgotPasswordForm = document.getElementById('forgotPasswordForm');
  const forgotPasswordEmailInput = document.getElementById('forgotPasswordEmail');
  const backToLoginFromForgot = document.getElementById('backToLoginFromForgot');
  const resetPasswordOverlay = document.getElementById('resetPasswordOverlay');
  const resetPasswordForm = document.getElementById('resetPasswordForm');
  const newPasswordInput = document.getElementById('newPassword');
  const confirmNewPasswordInput = document.getElementById('confirmNewPassword');
  const resetPasswordErrorMessage = document.getElementById('resetPasswordErrorMessage');
  const resetPasswordErrorText = document.getElementById('resetPasswordErrorText');
  const closeResetPasswordErrorBtn = document.getElementById('closeResetPasswordErrorBtn');
  const backToLoginFromReset = document.getElementById('backToLoginFromReset');
  const passwordChangedOverlay = document.getElementById('passwordChangedOverlay');
  const goToLoginFromChangedBtn = document.getElementById('goToLoginFromChangedBtn');
  const subscriptionOverlay = document.getElementById('subscriptionOverlay');
  const closeSubscriptionOverlayBtn = document.getElementById('closeSubscriptionOverlayBtn');
  const subscribeBtnSidebar = document.getElementById('subscribeBtn');
  const planSelectButtons = document.querySelectorAll('.btn-plan-select');
  const purchaseConfirmationModal = document.getElementById('purchaseConfirmationModal');
  const closePurchaseModalBtn = document.getElementById('closePurchaseModalBtn');
  const selectedPlanNameModal = document.getElementById('selectedPlanNameModal');
  const confirmPurchaseBtn = document.getElementById('confirmPurchaseBtn');
  let currentPlanPurchaseLink = '#';
  const authActionRequiredModal = document.getElementById('authActionRequiredModal');
  const closeAuthActionModalBtn = document.getElementById('closeAuthActionModalBtn');
  const authActionLoginBtn = document.getElementById('authActionLoginBtn');
  const authActionRegisterBtn = document.getElementById('authActionRegisterBtn');
  const authActionGuestBtn = document.getElementById('authActionGuestBtn');
  const authActionModalTitle = document.getElementById('authActionModalTitle');
  const attachmentLimitModal = document.getElementById('attachmentLimitModal');
  const closeAttachmentLimitModalBtn = document.getElementById('closeAttachmentLimitModalBtn');
  const limitExceededModal1 = document.getElementById('limitExceededModal1');
  const limitExceededModal2 = document.getElementById('limitExceededModal2');
  const limitExceededModalPhoto = document.getElementById('limitExceededModalPhoto');
  const limitExceededModalSmart = document.getElementById('limitExceededModalSmart');
  const triggerModal1Btn = document.getElementById('triggerModal1');
  const triggerModal2Btn = document.getElementById('triggerModal2');
  const triggerModalPhotoBtn = document.getElementById('triggerModalPhoto');
  const triggerModalSmartBtn = document.getElementById('triggerModalSmart');
  const deleteChatConfirmModal = document.getElementById('deleteChatConfirmModal');
  const chatNameToDeleteSpan = document.getElementById('chatNameToDelete');
  const cancelDeleteChatBtn = document.getElementById('cancelDeleteChatBtn');
  const confirmDeleteChatBtn = document.getElementById('confirmDeleteChatBtn');
  const closeDeleteConfirmModalBtn = document.getElementById('closeDeleteConfirmModalBtn');
  let chatIdToDelete = null;

  let messageListContainer;
  if (chatArea) {
    const inputArea = chatArea.querySelector('.input-area');
    if (inputArea) {
      messageListContainer = document.createElement('div');
      messageListContainer.classList.add('message-list-container');
      messageListContainer.style.display = 'none';
      chatArea.insertBefore(messageListContainer, inputArea);
    }
  }

  function loadGuestRequestsCount() {
    const count = localStorage.getItem('guestRequests');
    guestRequestsCount = count ? parseInt(count, 10) : 0;
  }

  loadGuestRequestsCount();

  function saveGuestRequestsCount() {
    localStorage.setItem('guestRequests', guestRequestsCount.toString());
  }

  function showAuthActionRequiredModal(isLimitReached = false) {
    hideAllScreens();
    if (authActionRequiredModal) {
      authActionRequiredModal.style.display = 'flex';
      if (authActionGuestBtn) {
        authActionGuestBtn.style.display = isLimitReached ? 'none' : 'block';
      }
      if (authActionModalTitle) {
        authActionModalTitle.textContent = isLimitReached ? "Лимит гостевых запросов исчерпан. Войдите или создайте аккаунт." : "Нужен аккаунт, что бы пользоваться нейросетью";
      }
    }
    document.body.classList.add('modal-open');
  }

  actionButtons.forEach(button => {
    button.addEventListener('click', async () => {
      if (!isLoggedIn && !isGuestMode) {
        if (!button.classList.contains('active')) {
          showAuthActionRequiredModal(guestRequestsCount >= GUEST_REQUEST_LIMIT);
        }
        return;
      }
      if (isGuestMode && guestRequestsCount >= GUEST_REQUEST_LIMIT && !button.classList.contains('active')) {
        showAuthActionRequiredModal(true);
        return;
      }
      if (isGuestMode && !button.classList.contains('btn-quick') && !button.classList.contains('active')) {
        alert("Гостевой режим поддерживает только 'Быструю' модель.");
        return;
      }
      if (button.classList.contains('active')) {
        return;
      }
      const modelKey = button.dataset.modelKey;
      if (!modelKey) {
        console.error("Model key not found on button", button);
        return;
      }
      let changeModelSuccess = true;
      if (currentChatId && isLoggedIn) {
        const result = await handleApiRequest(`/api/chat/model`, 'POST', {
          chat_id: currentChatId,
          model_key: modelKey
        }, {}, false, true);
        if (result.success) {
          const chatIndex = userChats.findIndex(c => c.id === currentChatId);
          if (chatIndex > -1 && result.data && result.data.model_key) {
            userChats[chatIndex].model_key = result.data.model_key;
          }
        } else {
          alert(`Не удалось сменить модель: ${result.error}`);
          changeModelSuccess = false;
        }
      }
      if (changeModelSuccess) {
        actionButtons.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
        updateAttachButtonVisibility();
      }
    });
  });

  function updateAttachButtonVisibility() {
    if (!attachFileBtn) return;
    const activeAnalyzeButton = document.querySelector('.action-buttons .btn.btn-analyze-photo.active');
    if (activeAnalyzeButton && (isLoggedIn || (isGuestMode && guestRequestsCount < GUEST_REQUEST_LIMIT))) {
      attachFileBtn.style.display = 'inline-flex';
    } else {
      attachFileBtn.style.display = 'none';
      clearAllAttachments();
    }
  }

  function appendMessage(type, data, prepend = false) {
    if (!messageListContainer) return;
    let messageElement;
    if (type === 'user') {
      messageElement = document.createElement('div');
      messageElement.classList.add('chat-message', 'user-message');
      messageElement.textContent = data.text;
    } else if (type === 'user-image') {
      messageElement = document.createElement('div');
      messageElement.classList.add('chat-message', 'user-message', 'image-only');
      const img = document.createElement('img');
      img.classList.add('sent-image');
      img.src = data.src;
      img.alt = "User attachment";
      messageElement.appendChild(img);
    } else if (type === 'bot-thinking') {
      messageElement = document.createElement('div');
      messageElement.classList.add('chat-message', 'bot-message', 'bot-message-thinking');
      const label = document.createElement('div');
      label.classList.add('message-label');
      label.textContent = data.label;
      messageElement.appendChild(label);
      const content = document.createElement('div');
      content.textContent = data.content;
      messageElement.appendChild(content);
    } else if (type === 'bot-collapsible-think') {
      messageElement = document.createElement('div');
      messageElement.classList.add('bot-message-thinking-collapsible');
      const header = document.createElement('div');
      header.classList.add('thinking-header');
      header.textContent = data.header_title || 'Показать/скрыть мысли ИИ';
      const arrow = document.createElement('span');
      arrow.classList.add('icon-think-arrow');
      arrow.innerHTML = '▼';
      header.appendChild(arrow);
      const contentDiv = document.createElement('div');
      contentDiv.classList.add('thinking-content');
      contentDiv.textContent = data.content;
      messageElement.appendChild(header);
      messageElement.appendChild(contentDiv);
      header.addEventListener('click', () => {
        messageElement.classList.toggle('open');
      });
    } else if (type === 'bot-response') {
      messageElement = document.createElement('div');
      messageElement.classList.add('chat-message', 'bot-message');
      messageElement.textContent = data.text;
    }
    if (messageElement) {
      if (prepend) {
        messageListContainer.insertBefore(messageElement, messageListContainer.firstChild);
      } else {
        messageListContainer.appendChild(messageElement);
      }
    }
    if (messageListContainer && !prepend) {
      requestAnimationFrame(() => {
        messageListContainer.scrollTop = messageListContainer.scrollHeight;
      });
    }
  }

  function renderAttachmentPreviews() {
    if (!attachmentPreviewContainer) return;
    attachmentPreviewContainer.innerHTML = '';
    if (attachedFilesData.length === 0) {
      attachmentPreviewContainer.style.display = 'none';
      return;
    }
    attachedFilesData.forEach(fileData => {
      const previewItem = document.createElement('div');
      previewItem.classList.add('preview-item');
      const img = document.createElement('img');
      img.src = fileData.src;
      img.alt = "Preview";
      const deleteBtn = document.createElement('button');
      deleteBtn.classList.add('icon-btn', 'btn-delete-attachment');
      deleteBtn.setAttribute('aria-label', 'Remove attachment');
      deleteBtn.dataset.previewId = fileData.id;
      const deleteIcon = document.createElement('img');
      deleteIcon.src = './img/deleteBtn.svg';
      deleteIcon.alt = 'Remove';
      deleteBtn.appendChild(deleteIcon);
      deleteBtn.addEventListener('click', () => {
        attachedFilesData = attachedFilesData.filter(f => f.id !== fileData.id);
        renderAttachmentPreviews();
      });
      previewItem.appendChild(img);
      previewItem.appendChild(deleteBtn);
      attachmentPreviewContainer.appendChild(previewItem);
    });
    attachmentPreviewContainer.style.display = 'flex';
  }

  function clearAllAttachments() {
    attachedFilesData = [];
    if (fileAttachmentInput) fileAttachmentInput.value = '';
    renderAttachmentPreviews();
  }

  async function loadChatMessages(chatId) {
    if (!chatId || (!isLoggedIn && !isGuestMode)) return;
    if (messageListContainer) messageListContainer.innerHTML = '';
    if (isGuestMode) {
      if (welcomeMessage) welcomeMessage.style.display = 'block';
      if (messageListContainer) messageListContainer.style.display = 'none';
      if (chatArea) chatArea.classList.remove('chat-active');
      return;
    }
    const result = await handleApiRequest(`/api/chat/talk/${chatId}`, 'GET', null, {}, false, true);
    if (result.success && Array.isArray(result.data)) {
      const messagesInChronologicalOrder = result.data.reverse();
      messagesInChronologicalOrder.forEach(msg => {
        const thinkRegex = /<think>([\s\S]*?)<\/think>/;
        let content = msg.content;
        const thinkMatch = content ? content.match(thinkRegex) : null;
        if (thinkMatch && thinkMatch[1]) {
          const thinkContent = thinkMatch[1].trim();
          content = content.replace(thinkRegex, '').trim();
          appendMessage('bot-collapsible-think', {
            header_title: 'Мысли ИИ (нажмите для просмотра)',
            content: thinkContent
          });
        }
        if (msg.role === 'user') {
          appendMessage('user', {text: content || ""});
        } else if (msg.role === 'bot') {
          if (content) {
            appendMessage('bot-response', {text: content});
          }
        }
      });
      if (welcomeMessage) welcomeMessage.style.display = 'none';
      if (messageListContainer) messageListContainer.style.display = 'flex';
      if (chatArea) chatArea.classList.add('chat-active');
      if (messageListContainer) {
        requestAnimationFrame(() => {
          messageListContainer.scrollTop = messageListContainer.scrollHeight;
        });
      }
    } else {
      console.error("Failed to load messages for chat " + chatId + ":", result.error);
      if (messageListContainer) messageListContainer.innerHTML = '<p style="text-align:center; color: #888;">Не удалось загрузить сообщения.</p>';
      if (welcomeMessage) welcomeMessage.style.display = 'none';
      if (messageListContainer) messageListContainer.style.display = 'flex';
      if (chatArea) chatArea.classList.add('chat-active');
    }
  }

  async function handleSendMessage() {
    if (!isLoggedIn && !isGuestMode) {
      showAuthActionRequiredModal(guestRequestsCount >= GUEST_REQUEST_LIMIT);
      return;
    }
    if (isGuestMode && guestRequestsCount >= GUEST_REQUEST_LIMIT) {
      showAuthActionRequiredModal(true);
      return;
    }
    const userInput = chatTextArea.value.trim();
    const activeModeButton = document.querySelector('.action-buttons .btn.active');
    let isSmartMode = false;
    let isAnalyzePhotoMode = false;
    if (activeModeButton) {
      isSmartMode = activeModeButton.classList.contains('btn-smart');
      isAnalyzePhotoMode = activeModeButton.classList.contains('btn-analyze-photo');
    }
    if (isGuestMode && (isSmartMode || isAnalyzePhotoMode)) {
      alert("В гостевом режиме доступна только 'Быстрая' модель и текстовые запросы.");
      actionButtons.forEach(btn => btn.classList.remove('active'));
      document.querySelector('.action-buttons .btn-quick').classList.add('active');
      updateAttachButtonVisibility();
      return;
    }
    if (userInput === '' && attachedFilesData.length === 0) {
      alert('Пожалуйста, введите сообщение или прикрепите файл.');
      return;
    }
    if (isAnalyzePhotoMode && attachedFilesData.length === 0) {
      alert('Для режима "Анализ фото" необходимо прикрепить изображение.');
      return;
    }
    if (!isAnalyzePhotoMode && attachedFilesData.length > 0) {
      alert('Прикрепление файлов доступно только в режиме "Анализ фото". Файлы не будут отправлены.');
      clearAllAttachments();
      if (userInput === '') return;
    }
    if (chatArea && !chatArea.classList.contains('chat-active')) {
      if (welcomeMessage) welcomeMessage.style.display = 'none';
      if (messageListContainer) messageListContainer.style.display = 'flex';
      chatArea.classList.add('chat-active');
    }
    const effectiveChatId = isGuestMode ? null : currentChatId;
    const selectedChat = userChats.find(chat => chat.id === effectiveChatId);
    if (chatTitleHeader) {
      if (isGuestMode) {
        chatTitleHeader.textContent = "Гостевой чат";
      } else if (effectiveChatId && selectedChat && selectedChat.title) {
        chatTitleHeader.textContent = selectedChat.title;
      } else if (!effectiveChatId) {
        chatTitleHeader.textContent = "Новый чат...";
      } else if (effectiveChatId && selectedChat && !selectedChat.title) {
        chatTitleHeader.textContent = `Чат от ${new Date(selectedChat.created_at).toLocaleString()}`;
      }
      chatTitleHeader.style.display = 'block';
    }
    let endpoint;
    let requestBody;
    let isFormDataRequest = false;
    let headers = {};
    if (isAnalyzePhotoMode && attachedFilesData.length > 0) {
      endpoint = `/api/chat/image`;
      if (isLoggedIn && effectiveChatId !== null) {
        endpoint += `?chat_id=${effectiveChatId}`;
      } else if (isGuestMode && !effectiveChatId) {
      } else if (isLoggedIn && !effectiveChatId) {
      } else {
        console.error("Невозможно отправить изображение без ID чата для существующего чата.");
        alert("Ошибка отправки изображения.");
        return;
      }
      requestBody = new FormData();
      requestBody.append('prompt', userInput || "");
      if (userInput) {
        appendMessage('user', {text: userInput});
      }
      attachedFilesData.forEach(fileData => {
        if (fileData.fileObject instanceof File) {
          requestBody.append('file', fileData.fileObject, fileData.fileObject.name);
          appendMessage('user-image', {src: fileData.src});
        }
      });
      isFormDataRequest = true;
    } else {
      endpoint = '/api/chat/message';
      requestBody = {chat_id: effectiveChatId, message: userInput};
      if (userInput) appendMessage('user', {text: userInput});
      isFormDataRequest = false;
    }
    if (chatTextArea) chatTextArea.value = '';
    clearAllAttachments();
    if (isSmartMode && (isLoggedIn || (isGuestMode && guestRequestsCount < GUEST_REQUEST_LIMIT))) {
      appendMessage('bot-thinking', {label: "Мысли", content: "Хмм..."});
    }
    const requiresAuthForRequest = isLoggedIn || isGuestMode;
    const result = await handleApiRequest(endpoint, 'POST', requestBody, headers, isFormDataRequest, requiresAuthForRequest);
    if (result.success && result.data) {
      let botAnswer = result.data.answer;
      const newChatIdFromServer = result.data.chat_id;
      const thinkRegex = /<think>([\s\S]*?)<\/think>/;
      const thinkMatch = botAnswer ? botAnswer.match(thinkRegex) : null;
      const thinkingMessageOld = messageListContainer ? messageListContainer.querySelector('.bot-message-thinking') : null;
      if (thinkingMessageOld) thinkingMessageOld.remove();
      if (thinkMatch && thinkMatch[1]) {
        const thinkContent = thinkMatch[1].trim();
        botAnswer = botAnswer.replace(thinkRegex, '').trim();
        appendMessage('bot-collapsible-think', {
          header_title: 'Мысли ИИ (нажмите для просмотра)',
          content: thinkContent
        });
      }
      if (botAnswer) {
        appendMessage('bot-response', {text: botAnswer});
      }
      if (isGuestMode) {
        guestRequestsCount++;
        saveGuestRequestsCount();
        if (guestRequestsCount >= GUEST_REQUEST_LIMIT) {
          appendMessage('bot-response', {text: "Лимит гостевых запросов исчерпан. Пожалуйста, войдите или зарегистрируйтесь."});
          showAuthActionRequiredModal(true);
        }
      } else if (isLoggedIn) {
        if (newChatIdFromServer && (!currentChatId || currentChatId !== newChatIdFromServer)) {
          currentChatId = newChatIdFromServer;
          console.log("Chat ID updated/set to:", currentChatId);
          await loadUserChats();
        } else if (currentChatId) {
          const chatIndex = userChats.findIndex(c => c.id === currentChatId);
          if (chatIndex > -1) {
            userChats[chatIndex].last_interaction_at = new Date().toISOString();
            if (result.data.model_key) userChats[chatIndex].model_key = result.data.model_key;
            renderChatList(userChats);
          }
        }
      }
    } else {
      console.error("Error sending message/image:", result.error, result.details);
      const thinkingMessageOld = messageListContainer ? messageListContainer.querySelector('.bot-message-thinking') : null;
      if (thinkingMessageOld) thinkingMessageOld.remove();
      appendMessage('bot-response', {text: `Извините, произошла ошибка: ${result.error || 'Неизвестная ошибка'}`});
    }
  }

  if (attachFileBtn) {
    attachFileBtn.addEventListener('click', () => {
      if (!isLoggedIn && !isGuestMode) {
        showAuthActionRequiredModal(guestRequestsCount >= GUEST_REQUEST_LIMIT);
        return;
      }
      if (isGuestMode && guestRequestsCount >= GUEST_REQUEST_LIMIT) {
        showAuthActionRequiredModal(true);
        return;
      }
      if (fileAttachmentInput) fileAttachmentInput.click();
    });
  }
  if (fileAttachmentInput) {
    fileAttachmentInput.addEventListener('change', (event) => {
      const files = event.target.files;
      if (!files || files.length === 0) return;
      if (attachedFilesData.length + files.length > MAX_ATTACHMENTS) {
        showAttachmentLimitModal();
        event.target.value = '';
        return;
      }
      let filesProcessed = 0;
      const newFilesToProcess = files.length;
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (file.type.startsWith('image/')) {
          const reader = new FileReader();
          reader.onload = (e) => {
            const fileId = Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            attachedFilesData.push({id: fileId, src: e.target.result, fileObject: file});
            filesProcessed++;
            if (filesProcessed === newFilesToProcess) renderAttachmentPreviews();
          }
          reader.readAsDataURL(file);
        } else {
          filesProcessed++;
          if (filesProcessed === newFilesToProcess) renderAttachmentPreviews();
        }
      }
      event.target.value = '';
    });
  }
  if (sendButton) sendButton.addEventListener('click', handleSendMessage);
  if (chatTextArea) {
    chatTextArea.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        handleSendMessage();
      }
    });
  }

  function updateSidebarUI(isClosed) {
    if (!sidebar || !sidebarOpenBtnGlobal || !sidebarToggleBtnLocal || !toggleImage) return;

    if (isClosed) {
      sidebar.classList.add('closed');
      sidebarOpenBtnGlobal.style.display = 'inline-flex';
      sidebarToggleBtnLocal.style.display = 'none';
      toggleImage.classList.remove('rotated');
    } else {
      sidebar.classList.remove('closed');
      sidebarOpenBtnGlobal.style.display = 'none';
      sidebarToggleBtnLocal.style.display = 'inline-flex';
      toggleImage.classList.add('rotated');
    }
  }

  if (sidebarToggleBtnLocal) {
    sidebarToggleBtnLocal.addEventListener('click', () => {
      updateSidebarUI(true);
    });
  }
  if (sidebarOpenBtnGlobal) {
    sidebarOpenBtnGlobal.addEventListener('click', () => {
      updateSidebarUI(false);
    });
  }

  window.addEventListener('resize', () => {
    if (window.innerWidth > 768) {
      updateSidebarUI(sidebar ? sidebar.classList.contains('closed') : true);
    } else {
      if (sidebar && !sidebar.classList.contains('opened-mobile')) {
        updateSidebarUI(true);
      } else if (sidebar && sidebar.classList.contains('opened-mobile')) {
        updateSidebarUI(false);
      }
    }
  });
  updateSidebarUI(sidebar ? sidebar.classList.contains('closed') : true);


  function hideAllScreens() {
    if (loginOverlay) loginOverlay.style.display = 'none';
    if (registerOverlay) registerOverlay.style.display = 'none';
    if (verifyEmailOverlay) verifyEmailOverlay.style.display = 'none';
    if (forgotPasswordOverlay) forgotPasswordOverlay.style.display = 'none';
    if (resetPasswordOverlay) resetPasswordOverlay.style.display = 'none';
    if (passwordChangedOverlay) passwordChangedOverlay.style.display = 'none';
    if (subscriptionOverlay) subscriptionOverlay.style.display = 'none';
    if (purchaseConfirmationModal) purchaseConfirmationModal.style.display = 'none';
    if (authActionRequiredModal) authActionRequiredModal.style.display = 'none';
    if (attachmentLimitModal) attachmentLimitModal.style.display = 'none';
    if (limitExceededModal1) limitExceededModal1.style.display = 'none';
    if (limitExceededModal2) limitExceededModal2.style.display = 'none';
    if (limitExceededModalPhoto) limitExceededModalPhoto.style.display = 'none';
    if (limitExceededModalSmart) limitExceededModalSmart.style.display = 'none';
    if (appLayout) appLayout.style.display = 'none';
    document.body.classList.remove('modal-open');
    hideRegisterError();
    hideVerifyError();
    hideResetPasswordError();
    if (deleteChatConfirmModal) deleteChatConfirmModal.style.display = 'none';
  }

  function showLoginScreen() {
    hideAllScreens();
    if (loginOverlay) loginOverlay.style.display = 'flex';
  }

  function showRegisterScreen() {
    hideAllScreens();
    if (registerOverlay) registerOverlay.style.display = 'flex';
  }

  function showVerifyEmailScreen() {
    hideAllScreens();
    if (verifyEmailOverlay) verifyEmailOverlay.style.display = 'flex';
    if (verificationEmailDisplay) verificationEmailDisplay.textContent = userRegisteredEmail;
    codeInputs.forEach(input => input.value = '');
    if (codeInputs.length > 0) codeInputs[0].focus();
  }

  function showForgotPasswordScreen() {
    hideAllScreens();
    if (forgotPasswordOverlay) forgotPasswordOverlay.style.display = 'flex';
  }

  function showResetPasswordScreen() {
    hideAllScreens();
    if (resetPasswordOverlay) resetPasswordOverlay.style.display = 'flex';
    hideResetPasswordError();
  }

  function showPasswordChangedScreen() {
    hideAllScreens();
    if (passwordChangedOverlay) passwordChangedOverlay.style.display = 'flex';
  }

  function showSubscriptionScreen() {
    hideAllScreens();
    if (subscriptionOverlay) subscriptionOverlay.style.display = 'flex';
  }

  function showPurchaseConfirmationModal(planName, planPrice) {
    if (subscriptionOverlay && subscriptionOverlay.style.display === 'flex') {
      subscriptionOverlay.style.filter = 'blur(5px)';
    } else if (appLayout && appLayout.style.display === 'flex') {
      appLayout.style.filter = 'blur(5px)';
    }
    document.body.classList.add('modal-open');
    if (selectedPlanNameModal) {
      selectedPlanNameModal.textContent = planName;
    }
    if (purchaseConfirmationModal) purchaseConfirmationModal.style.display = 'flex';
  }

  function hidePurchaseConfirmationModal() {
    if (purchaseConfirmationModal) purchaseConfirmationModal.style.display = 'none';
    document.body.classList.remove('modal-open');
    if (subscriptionOverlay) subscriptionOverlay.style.filter = 'none';
    if (appLayout) appLayout.style.filter = 'none';
  }

  function hideAuthActionRequiredModal() {
    if (authActionRequiredModal) authActionRequiredModal.style.display = 'none';
    document.body.classList.remove('modal-open');
    if (!isLoggedIn && !isGuestMode) showAppLayout();
    renderAuthState();
  }

  function showAttachmentLimitModal() {
    hideAllScreens();
    if (attachmentLimitModal) attachmentLimitModal.style.display = 'flex';
    document.body.classList.add('modal-open');
  }

  function hideAttachmentLimitModal() {
    if (attachmentLimitModal) attachmentLimitModal.style.display = 'none';
    document.body.classList.remove('modal-open');
    showAppLayout();
    renderAuthState();
  }

  function showLimitModal(modalElement) {
    hideAllScreens();
    if (modalElement) modalElement.style.display = 'flex';
    document.body.classList.add('modal-open');
  }

  function hideLimitModal(modalElement) {
    if (modalElement) modalElement.style.display = 'none';
    document.body.classList.remove('modal-open');
    showAppLayout();
    renderAuthState();
  }

  function showAppLayout() {
    hideAllScreens();
    if (appLayout) appLayout.style.display = 'flex';
  }

  function showRegisterError(message) {
    if (registerErrorText) registerErrorText.textContent = message;
    if (registerErrorMessage) registerErrorMessage.style.display = 'flex';
  }

  function hideRegisterError() {
    if (registerErrorMessage) registerErrorMessage.style.display = 'none';
    if (registerErrorText) registerErrorText.textContent = '';
  }

  function showVerifyError(message) {
    if (verifyErrorText) verifyErrorText.textContent = message;
    if (verifyErrorMessage) verifyErrorMessage.style.display = 'flex';
  }

  function hideVerifyError() {
    if (verifyErrorMessage) verifyErrorMessage.style.display = 'none';
    if (verifyErrorText) verifyErrorText.textContent = '';
  }

  function showResetPasswordError(message) {
    if (resetPasswordErrorText) resetPasswordErrorText.textContent = message;
    if (resetPasswordErrorMessage) resetPasswordErrorMessage.style.display = 'flex';
  }

  function hideResetPasswordError() {
    if (resetPasswordErrorMessage) resetPasswordErrorMessage.style.display = 'none';
    if (resetPasswordErrorText) resetPasswordErrorText.textContent = '';
  }

  function showDeleteChatConfirmModal(chatId, chatTitle) {
    chatIdToDelete = chatId;
    if (chatNameToDeleteSpan) chatNameToDeleteSpan.textContent = chatTitle || `Чат #${chatId}`;
    if (deleteChatConfirmModal) deleteChatConfirmModal.style.display = 'flex';
    document.body.classList.add('modal-open');
  }

  function hideDeleteChatConfirmModal() {
    if (deleteChatConfirmModal) deleteChatConfirmModal.style.display = 'none';
    document.body.classList.remove('modal-open');
    chatIdToDelete = null;
  }

  async function saveChatTitle(chatId, newTitle, nameSpan, editInput, listItem) {
    const result = await handleApiRequest(`/api/chat/title`, 'POST', {
      chat_id: chatId,
      title: newTitle
    }, {}, false, true);
    if (result.success && result.data) {
      nameSpan.textContent = result.data.title || newTitle;
      const chatInList = userChats.find(c => c.id === chatId);
      if (chatInList) {
        chatInList.title = result.data.title || newTitle;
      }
      renderChatList(userChats);
      if (currentChatId === chatId && chatTitleHeader) {
        chatTitleHeader.textContent = result.data.title || newTitle;
      }
    } else {
      alert("Не удалось сохранить название чата: " + (result.error || "Неизвестная ошибка"));
      editInput.value = nameSpan.textContent;
    }
    nameSpan.style.display = 'inline';
    editInput.style.display = 'none';
    listItem.classList.remove('editing');
  }

  function toggleChatTitleEdit(listItem, nameSpan, editInput, chatId) {
    const isEditing = listItem.classList.contains('editing');
    if (isEditing) {
      const newTitle = editInput.value.trim();
      if (newTitle && newTitle !== nameSpan.textContent) {
        saveChatTitle(chatId, newTitle, nameSpan, editInput, listItem);
      } else {
        nameSpan.style.display = 'inline';
        editInput.style.display = 'none';
        listItem.classList.remove('editing');
      }
    } else {
      nameSpan.style.display = 'none';
      editInput.style.display = 'inline-block';
      editInput.value = nameSpan.textContent;
      editInput.focus();
      editInput.select();
      listItem.classList.add('editing');
      const handleEditKeyDown = async (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const newTitle = editInput.value.trim();
          if (newTitle && newTitle !== nameSpan.textContent) {
            await saveChatTitle(chatId, newTitle, nameSpan, editInput, listItem);
          } else {
            nameSpan.style.display = 'inline';
            editInput.style.display = 'none';
            listItem.classList.remove('editing');
          }
          editInput.removeEventListener('keydown', handleEditKeyDown);
          editInput.removeEventListener('blur', handleEditBlur);
        } else if (e.key === 'Escape') {
          nameSpan.style.display = 'inline';
          editInput.style.display = 'none';
          listItem.classList.remove('editing');
          editInput.removeEventListener('keydown', handleEditKeyDown);
          editInput.removeEventListener('blur', handleEditBlur);
        }
      };
      const handleEditBlur = async () => {
        setTimeout(async () => {
          if (listItem.classList.contains('editing')) {
            const newTitle = editInput.value.trim();
            if (newTitle && newTitle !== nameSpan.textContent) {
              await saveChatTitle(chatId, newTitle, nameSpan, editInput, listItem);
            } else {
              nameSpan.style.display = 'inline';
              editInput.style.display = 'none';
              listItem.classList.remove('editing');
            }
            editInput.removeEventListener('keydown', handleEditKeyDown);
            editInput.removeEventListener('blur', handleEditBlur);
          }
        }, 100);
      };
      editInput.addEventListener('keydown', handleEditKeyDown);
      editInput.addEventListener('blur', handleEditBlur);
    }
  }

  function renderChatList(chatsToRender) {
    if (!chatListUl) return;
    chatListUl.innerHTML = '';
    if (!chatsToRender || chatsToRender.length === 0) {
      const noChatsLi = document.createElement('li');
      noChatsLi.textContent = 'Нет доступных чатов.';
      noChatsLi.style.padding = '8px 5px';
      noChatsLi.style.color = '#888';
      chatListUl.appendChild(noChatsLi);
      return;
    }
    chatsToRender.sort((a, b) => {
      if (a.is_active && !b.is_active) return -1;
      if (!a.is_active && b.is_active) return 1;
      return new Date(b.last_interaction_at) - new Date(a.last_interaction_at);
    });
    let activeChatFoundAndSet = false;
    chatsToRender.forEach(chat => {
      const li = document.createElement('li');
      li.classList.add('chat-item');
      li.dataset.chatId = chat.id;
      if (currentChatId === null && chat.is_active && !activeChatFoundAndSet) {
        currentChatId = chat.id;
        activeChatFoundAndSet = true;
      }
      if (chat.id === currentChatId) {
        li.classList.add('selected');
        if (chatTitleHeader) {
          chatTitleHeader.textContent = chat.title || `Чат от ${new Date(chat.created_at).toLocaleString()}` || `Чат #${chat.id}`;
          chatTitleHeader.style.display = 'block';
        }
      }
      const chatNameSpan = document.createElement('span');
      chatNameSpan.classList.add('chat-name');
      chatNameSpan.textContent = chat.title || `Чат от ${new Date(chat.created_at).toLocaleString()}` || `Чат #${chat.id}`;
      const editInput = document.createElement('input');
      editInput.type = 'text';
      editInput.classList.add('chat-name-edit-input');
      editInput.value = chatNameSpan.textContent;
      editInput.style.display = 'none';
      li.appendChild(chatNameSpan);
      li.appendChild(editInput);
      const chatActionsDiv = document.createElement('div');
      chatActionsDiv.classList.add('chat-actions');
      const deleteBtn = document.createElement('button');
      deleteBtn.classList.add('icon-btn', 'small-icon', 'btn-delete-chat');
      deleteBtn.innerHTML = '<span class="icon"><img src="./img/deleteBtn.svg" alt="Delete"></span>';
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        showDeleteChatConfirmModal(chat.id, chatNameSpan.textContent);
      });
      const editBtn = document.createElement('button');
      editBtn.classList.add('icon-btn', 'small-icon', 'btn-edit-chat-title');
      editBtn.innerHTML = '<span class="icon"><img src="./img/EditBtn.svg" alt="Edit"></span>';
      editBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleChatTitleEdit(li, chatNameSpan, editInput, chat.id);
      });
      chatActionsDiv.appendChild(deleteBtn);
      chatActionsDiv.appendChild(editBtn);
      li.appendChild(chatActionsDiv);
      li.addEventListener('click', async (e) => {
        if (e.target.closest('.chat-actions')) return;
        if (li.classList.contains('editing')) return;
        const clickedChatId = chat.id;
        const selectResult = await handleApiRequest(`/api/chat/select`, 'POST', {chat_id: clickedChatId}, {}, false, true);
        if (selectResult.success && selectResult.data) {
          currentChatId = selectResult.data.id;
          userChats = userChats.map(c => ({...c, is_active: c.id === currentChatId}));
          renderChatList(userChats);
          await loadChatMessages(currentChatId);
        } else {
          console.error("Ошибка при выборе чата на сервере:", selectResult.error);
          alert("Не удалось выбрать чат. Пожалуйста, попробуйте еще раз.");
        }
      });
      chatListUl.appendChild(li);
    });
  }

  async function loadUserChats() {
    if (!isLoggedIn || !authToken) {
      if (chatListUl) chatListUl.innerHTML = '<li>Для просмотра чатов войдите в аккаунт.</li>';
      return;
    }
    const listResult = await handleApiRequest('/api/chats', 'GET', null, {}, false, true);
    if (listResult.success) {
      if (Array.isArray(listResult.data)) {
        userChats = listResult.data;
      } else if (listResult.data && typeof listResult.data === 'object' && listResult.data !== null) {
        userChats = [listResult.data];
      } else if (listResult.data === null || (Array.isArray(listResult.data) && listResult.data.length === 0)) {
        userChats = [];
      } else {
        console.error("Unexpected data format for chats list:", listResult.data);
        userChats = [];
      }
      currentChatId = null;
      const activeChatFromList = userChats.find(chat => chat.is_active);
      if (activeChatFromList) {
        currentChatId = activeChatFromList.id;
      }
      renderChatList(userChats);
      if (currentChatId) {
        await loadChatMessages(currentChatId);
      } else if (userChats.length > 0 && chatListUl.firstChild && !chatListUl.firstChild.classList.contains('no-chats')) {
        const firstChatId = userChats[0].id;
        const selectResult = await handleApiRequest(`/api/chat/select`, 'POST', {chat_id: firstChatId}, {}, false, true);
        if (selectResult.success) {
          currentChatId = firstChatId;
          userChats = userChats.map(c => ({...c, is_active: c.id === currentChatId}));
          renderChatList(userChats);
          await loadChatMessages(currentChatId);
        }
      } else {
        if (welcomeMessage) welcomeMessage.style.display = 'block';
        if (chatArea) chatArea.classList.remove('chat-active');
        if (messageListContainer) messageListContainer.style.display = 'none';
        if (chatTitleHeader) chatTitleHeader.style.display = 'none';
      }
    } else {
      console.error("Failed to load chats list:", listResult.error);
      if (chatListUl) {
        const errorLi = document.createElement('li');
        errorLi.textContent = 'Не удалось загрузить чаты.';
        errorLi.style.padding = '8px 5px';
        errorLi.style.color = '#cc0000';
        chatListUl.innerHTML = '';
        chatListUl.appendChild(errorLi);
      }
    }
  }

  function renderUserProfile(profileData) {
    if (!profileData) {
      if (profileUsernameSpan) profileUsernameSpan.textContent = 'Email';
      if (subscriptionStatusSpan) subscriptionStatusSpan.textContent = 'free';
      if (subscriptionExpiresSpan) subscriptionExpiresSpan.textContent = '—';
      if (usageFastSpan) usageFastSpan.textContent = '0/0';
      if (usageSmartSpan) usageSmartSpan.textContent = '0/0';
      if (usageImageSpan) usageImageSpan.textContent = '0/0';
      return;
    }
    if (profileUsernameSpan) {
      profileUsernameSpan.textContent = profileData.email || 'Пользователь';
    }
    if (subscriptionStatusSpan) {
      subscriptionStatusSpan.textContent = profileData.status || 'free';
    }
    if (subscriptionExpiresSpan) {
      if (profileData.expires) {
        try {
          const date = new Date(profileData.expires);
          const day = String(date.getDate()).padStart(2, '0');
          const month = String(date.getMonth() + 1).padStart(2, '0');
          const year = date.getFullYear();
          subscriptionExpiresSpan.textContent = `${day}.${month}.${year}`;
        } catch (e) {
          subscriptionExpiresSpan.textContent = 'неверная дата';
          console.error("Invalid date format for expires", profileData.expires, e);
        }
      } else {
        subscriptionExpiresSpan.textContent = '—';
      }
    }
    if (profileData.usage) {
      if (usageFastSpan && profileData.usage.fast) {
        const limit = profileData.usage.fast.limit === null ? '∞' : (profileData.usage.fast.limit || 0);
        usageFastSpan.textContent = `${profileData.usage.fast.used || 0}/${limit}`;
      } else if (usageFastSpan) {
        usageFastSpan.textContent = '0/0';
      }
      if (usageSmartSpan && profileData.usage.smart) {
        const limit = profileData.usage.smart.limit === null ? '∞' : (profileData.usage.smart.limit || 0);
        usageSmartSpan.textContent = `${profileData.usage.smart.used || 0}/${limit}`;
      } else if (usageSmartSpan) {
        usageSmartSpan.textContent = '0/0';
      }
      if (usageImageSpan && profileData.usage.vision) {
        const limit = profileData.usage.vision.limit === null ? '∞' : (profileData.usage.vision.limit || 0);
        usageImageSpan.textContent = `${profileData.usage.vision.used || 0}/${limit}`;
      } else if (usageImageSpan) {
        usageImageSpan.textContent = '0/0';
      }
    } else {
      if (usageFastSpan) usageFastSpan.textContent = '0/0';
      if (usageSmartSpan) usageSmartSpan.textContent = '0/0';
      if (usageImageSpan) usageImageSpan.textContent = '0/0';
    }
  }

  async function loadAndRenderUserProfile() {
    if (!isLoggedIn || !authToken) return;
    const result = await handleApiRequest('/api/profile', 'GET', null, {}, false, true);
    if (result.success && result.data) {
      renderUserProfile(result.data);
    } else {
      console.error("Failed to load profile:", result.error);
      renderUserProfile(null);
    }
  }

  function handleNewChat() {
    if (!isLoggedIn && !isGuestMode) {
      showAuthActionRequiredModal(guestRequestsCount >= GUEST_REQUEST_LIMIT);
      return;
    }
    if (isGuestMode && guestRequestsCount >= GUEST_REQUEST_LIMIT) {
      showAuthActionRequiredModal(true);
      return;
    }
    currentChatId = null;
    if (messageListContainer) messageListContainer.innerHTML = '';
    if (welcomeMessage) welcomeMessage.style.display = 'block';
    if (chatArea) chatArea.classList.remove('chat-active');
    if (messageListContainer) messageListContainer.style.display = 'none';
    if (chatTitleHeader) {
      chatTitleHeader.textContent = isGuestMode ? "Гостевой чат" : "Новый чат";
      chatTitleHeader.style.display = 'block';
    }
    if (!isGuestMode) {
      renderChatList(userChats);
    } else {
      if (chatListUl) chatListUl.innerHTML = '<li style="padding: 8px 5px; color: #888;">Гостевой режим</li>';
    }
    if (chatTextArea) chatTextArea.focus();
  }

  function renderAuthState() {
    const isAnyAuthScreenOpen = (loginOverlay && loginOverlay.style.display === 'flex') || (registerOverlay && registerOverlay.style.display === 'flex') || (verifyEmailOverlay && verifyEmailOverlay.style.display === 'flex') || (forgotPasswordOverlay && forgotPasswordOverlay.style.display === 'flex') || (resetPasswordOverlay && resetPasswordOverlay.style.display === 'flex') || (passwordChangedOverlay && passwordChangedOverlay.style.display === 'flex');
    const isSubscriptionScreenOpen = subscriptionOverlay && subscriptionOverlay.style.display === 'flex';
    const isPurchaseModalOpen = purchaseConfirmationModal && purchaseConfirmationModal.style.display === 'flex';
    const isAuthActionModalOpen = authActionRequiredModal && authActionRequiredModal.style.display === 'flex';
    const isAttachmentLimitModalOpen = attachmentLimitModal && attachmentLimitModal.style.display === 'flex';
    const isGenericLimitModalOpen = (limitExceededModal1 && limitExceededModal1.style.display === 'flex') || (limitExceededModal2 && limitExceededModal2.style.display === 'flex') || (limitExceededModalPhoto && limitExceededModalPhoto.style.display === 'flex') || (limitExceededModalSmart && limitExceededModalSmart.style.display === 'flex');

    if (isLoggedIn) {
      isGuestMode = false;
      if (!isAnyAuthScreenOpen && !isSubscriptionScreenOpen && !isPurchaseModalOpen && !isAuthActionModalOpen && !isAttachmentLimitModalOpen && !isGenericLimitModalOpen) {
        showAppLayout();
      }
      requiresAuthElements.forEach(el => {
        if (el.classList.contains('user-profile-section') || el.classList.contains('chat-history-section') || el.classList.contains('btn-new-chat')) {
          el.style.display = 'block';
        } else {
          el.style.display = 'block';
        }
        if (el.classList.contains('user-profile-section')) {
          const userInfo = el.querySelector('.user-info');
          if (userInfo) userInfo.style.display = 'flex';
        }
      });
      if (authLinkSidebarFooter) authLinkSidebarFooter.style.display = 'none';
      if (logoutLinkSidebar) logoutLinkSidebar.style.display = 'flex';
      if (authLinkMainHeader) authLinkMainHeader.style.display = 'none';
      if (sidebar && sidebar.classList.contains('closed') && window.innerWidth <= 768) {
        updateSidebarUI(true);
      } else if (sidebar && !sidebar.classList.contains('closed') && window.innerWidth > 768) {
        updateSidebarUI(false);
      }
      loadUserChats();
      loadAndRenderUserProfile();
    } else if (isGuestMode) {
      if (!isAnyAuthScreenOpen && !isSubscriptionScreenOpen && !isPurchaseModalOpen && !isAuthActionModalOpen && !isAttachmentLimitModalOpen && !isGenericLimitModalOpen) {
        showAppLayout();
      }
      requiresAuthElements.forEach(el => el.style.display = 'none');
      if (authLinkSidebarFooter) authLinkSidebarFooter.style.display = 'flex';
      if (logoutLinkSidebar) logoutLinkSidebar.style.display = 'none';
      if (authLinkMainHeader) authLinkMainHeader.style.display = 'flex';
      if (chatListUl) chatListUl.innerHTML = '<li style="padding: 8px 5px; color: #888;">Гостевой режим</li>';
      currentChatId = null;
      userChats = [];
      if (chatTitleHeader) {
        chatTitleHeader.textContent = "Гостевой чат";
        chatTitleHeader.style.display = 'block';
      }
      renderUserProfile(null);
      actionButtons.forEach(btn => btn.classList.remove('active'));
      const quickButton = document.querySelector('.action-buttons .btn-quick');
      if (quickButton) quickButton.classList.add('active');
      if (sidebar && window.innerWidth <= 768) updateSidebarUI(true);
      else if (sidebar) updateSidebarUI(sidebar.classList.contains('closed'));

    } else {
      if (!isAnyAuthScreenOpen && !isSubscriptionScreenOpen && !isPurchaseModalOpen && !isAuthActionModalOpen && !isAttachmentLimitModalOpen && !isGenericLimitModalOpen) {
        showAppLayout();
      }
      requiresAuthElements.forEach(el => el.style.display = 'none');
      if (chatListUl) chatListUl.innerHTML = '';
      currentChatId = null;
      userChats = [];
      if (chatTitleHeader) chatTitleHeader.style.display = 'none';
      renderUserProfile(null);
      if (authLinkSidebarFooter) authLinkSidebarFooter.style.display = 'flex';
      if (logoutLinkSidebar) logoutLinkSidebar.style.display = 'none';
      if (authLinkMainHeader) authLinkMainHeader.style.display = 'flex';
      if (chatArea && chatArea.classList.contains('chat-active')) {
        chatArea.classList.remove('chat-active');
        if (welcomeMessage) welcomeMessage.style.display = 'block';
        if (messageListContainer) {
          messageListContainer.innerHTML = '';
          messageListContainer.style.display = 'none';
        }
        clearAllAttachments();
        if (chatTextArea) chatTextArea.value = '';
      }
      if (sidebar && window.innerWidth <= 768) updateSidebarUI(true);
      else if (sidebar) updateSidebarUI(sidebar.classList.contains('closed'));
    }
    updateAttachButtonVisibility();
  }

  async function handleApiRequest(url, method = 'POST', body = null, headers = {}, isFormData = false, requiresAuth = true) {
    const defaultHeaders = {'Accept': 'application/json',};
    let effectiveAuthToken = requiresAuth ? (isLoggedIn ? authToken : guestAuthToken) : null;
    if (body && !isFormData && !(body instanceof URLSearchParams)) {
      defaultHeaders['Content-Type'] = 'application/json';
    }
    if (effectiveAuthToken) {
      defaultHeaders['Authorization'] = `Bearer ${effectiveAuthToken}`;
    }
    const finalHeaders = {...defaultHeaders, ...headers};
    try {
      const options = {method: method, headers: finalHeaders, mode: 'cors'};
      if (body) {
        if (isFormData || body instanceof URLSearchParams) {
          options.body = body;
        } else {
          options.body = JSON.stringify(body);
        }
      }
      const response = await fetch(API_BASE_URL + url, options);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({detail: `Server error: ${response.status}. Response not JSON.`}));
        console.error('API Error Response:', response.status, errorData);
        let errorMessage = `Server error: ${response.status}`;
        if (errorData.detail && Array.isArray(errorData.detail) && errorData.detail.length > 0 && errorData.detail[0].msg) {
          errorMessage = errorData.detail[0].msg;
        } else if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        }
        return {success: false, error: errorMessage, status: response.status, details: errorData.detail};
      }
      if (response.status === 204 || response.headers.get("content-length") === "0") {
        return {success: true, data: null};
      }
      const data = await response.json();
      return {success: true, data: data};
    } catch (error) {
      console.error('Network or other error:', error);
      return {success: false, error: 'Network error or unable to connect to the server.'};
    }
  }

  async function handleLoginAttempt() {
    const email = loginEmailInput ? loginEmailInput.value : '';
    const password = loginPasswordInput ? loginPasswordInput.value : '';
    if (!email || !password) {
      alert("Пожалуйста, введите Email и пароль.");
      return;
    }
    const formData = new URLSearchParams();
    formData.append('grant_type', 'password');
    formData.append('username', email);
    formData.append('password', password);
    formData.append('scope', '');
    formData.append('client_id', '');
    formData.append('client_secret', '');
    const result = await handleApiRequest('/api/login/email', 'POST', formData, {'Content-Type': 'application/x-www-form-urlencoded'}, true, false);
    if (result.success && result.data.access_token) {
      authToken = result.data.access_token;
      localStorage.setItem('authToken', authToken);
      isLoggedIn = true;
      isGuestMode = false;
      showAppLayout();
      renderAuthState();
      console.log("User logged in successfully. Token:", authToken);
      if (loginEmailInput) loginEmailInput.value = '';
      if (loginPasswordInput) loginPasswordInput.value = '';
    } else {
      alert(result.error || "Неверный Email или пароль.");
    }
  }

  async function handleRegistrationAttempt() {
    const email = registerEmailInput ? registerEmailInput.value : '';
    const password = registerPasswordInput ? registerPasswordInput.value : '';
    const confirmPassword = registerConfirmPasswordInput ? registerConfirmPasswordInput.value : '';
    hideRegisterError();
    if (!email || !password || !confirmPassword) {
      showRegisterError("Пожалуйста, заполните все поля.");
      return;
    }
    if (password !== confirmPassword) {
      showRegisterError("Пароли не совпадают");
      return;
    }
    const result = await handleApiRequest('/api/register', 'POST', {email, password}, {}, false, false);
    if (result.success) {
      userRegisteredEmail = email;
      console.log("Registration request successful for:", email, "Proceeding to email verification.");
      showVerifyEmailScreen();
      if (registerEmailInput) registerEmailInput.value = '';
      if (registerPasswordInput) registerPasswordInput.value = '';
      if (registerConfirmPasswordInput) registerConfirmPasswordInput.value = '';
    } else {
      showRegisterError(result.error || "Ошибка регистрации.");
    }
  }

  async function handleVerifyCodeAttempt() {
    let enteredCode = "";
    codeInputs.forEach(input => {
      enteredCode += input.value;
    });
    hideVerifyError();
    if (enteredCode.length !== 6) {
      showVerifyError("Пожалуйста, введите 6-значный код.");
      return;
    }
    const result = await handleApiRequest('/api/confirm', 'POST', {
      email: userRegisteredEmail,
      code: enteredCode
    }, {}, false, false);
    if (result.success) {
      console.log("Email verified successfully with code:", enteredCode);
      alert("Почта успешно подтверждена! Теперь вы можете войти.");
      showLoginScreen();
    } else {
      showVerifyError(result.error || "Неверный код подтверждения.");
      codeInputs.forEach(input => input.value = '');
      if (codeInputs.length > 0) codeInputs[0].focus();
    }
  }

  function handleForgotPasswordAttempt() {
    const email = forgotPasswordEmailInput ? forgotPasswordEmailInput.value : '';
    if (!email) {
      alert("Пожалуйста, введите ваш Email.");
      return;
    }
    console.log("Forgot password attempt for:", email);
    alert("Инструкции по сбросу пароля отправлены на " + email + " (симуляция).");
    showResetPasswordScreen();
    if (forgotPasswordEmailInput) forgotPasswordEmailInput.value = '';
  }

  function handleResetPasswordAttempt() {
    const newPassword = newPasswordInput ? newPasswordInput.value : '';
    const confirmNew = confirmNewPasswordInput ? confirmNewPasswordInput.value : '';
    hideResetPasswordError();
    if (!newPassword || !confirmNew) {
      showResetPasswordError("Пожалуйста, заполните оба поля пароля.");
      return;
    }
    if (newPassword !== confirmNew) {
      showResetPasswordError("Пароли не совпадают.");
      return;
    }
    console.log("Password reset successful (simulated)");
    showPasswordChangedScreen();
    if (newPasswordInput) newPasswordInput.value = '';
    if (confirmNewPasswordInput) confirmNewPasswordInput.value = '';
  }

  function handleLogout() {
    isLoggedIn = false;
    isGuestMode = false;
    authToken = null;
    guestAuthToken = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('guestRequests');
    guestRequestsCount = 0;
    showAppLayout();
    renderAuthState();
    console.log("User logged out");
  }

  function initializeGoogleSignIn() {
    if (typeof google === 'undefined' || typeof google.accounts === 'undefined' || typeof google.accounts.id === 'undefined') {
      console.warn("Google Identity Services library not loaded yet or accounts.id not ready. Retrying...");
      setTimeout(initializeGoogleSignIn, 1000);
      return;
    }
    try {
      google.accounts.id.initialize({client_id: GOOGLE_CLIENT_ID, callback: handleGoogleCredentialResponse,});
      if (googleLoginButtons) {
        googleLoginButtons.forEach(button => {
          button.addEventListener('click', () => {
            console.log("Login with Google button clicked");
            google.accounts.id.prompt((notification) => {
              if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
                console.warn("Google Sign-In prompt was not displayed or skipped:", notification.getNotDisplayedReason() || notification.getSkippedReason());
              }
            });
          });
        });
      }
    } catch (error) {
      console.error("Error initializing Google Sign-In:", error);
    }
  }

  async function handleGoogleCredentialResponse(response) {
    console.log("Google Credential Response Received:", response);
    if (response.credential) {
      console.log("Encoded JWT ID token: " + response.credential);
      const result = await handleApiRequest('/api/login/google', 'POST', {id_token: response.credential}, {}, false, false);
      if (result.success && result.data && result.data.access_token) {
        authToken = result.data.access_token;
        localStorage.setItem('authToken', authToken);
        isLoggedIn = true;
        isGuestMode = false;
        showAppLayout();
        renderAuthState();
        console.log("User logged in successfully via Google. App Token:", authToken);
        if (loginEmailInput) loginEmailInput.value = '';
        if (loginPasswordInput) loginPasswordInput.value = '';
        if (registerEmailInput) registerEmailInput.value = '';
        if (registerPasswordInput) registerPasswordInput.value = '';
        if (registerConfirmPasswordInput) registerConfirmPasswordInput.value = '';
      } else {
        console.error("Google Sign-In failed on backend:", result.error, result.details);
        alert("Ошибка входа через Google: " + (result.error || "Не удалось войти."));
      }
    } else {
      console.error("Google Sign-In response did not contain credential.");
      alert("Ошибка ответа от Google. Попробуйте еще раз.");
    }
  }

  if (authLinkSidebarFooter) {
    authLinkSidebarFooter.addEventListener('click', (e) => {
      e.preventDefault();
      showLoginScreen();
    });
  }
  if (authLinkMainHeader) {
    authLinkMainHeader.addEventListener('click', (e) => {
      e.preventDefault();
      showLoginScreen();
    });
  }
  if (loginForm) {
    loginForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleLoginAttempt();
    });
  }
  if (registerForm) {
    registerForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleRegistrationAttempt();
    });
  }
  if (verifyCodeForm) {
    verifyCodeForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleVerifyCodeAttempt();
    });
  }
  if (forgotPasswordForm) {
    forgotPasswordForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleForgotPasswordAttempt();
    });
  }
  if (resetPasswordForm) {
    resetPasswordForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleResetPasswordAttempt();
    });
  }
  if (goToLoginFromChangedBtn) {
    goToLoginFromChangedBtn.addEventListener('click', (e) => {
      e.preventDefault();
      showLoginScreen();
    });
  }
  if (logoutLinkSidebar) {
    logoutLinkSidebar.addEventListener('click', (e) => {
      e.preventDefault();
      handleLogout();
    });
  }
  if (switchToRegisterLink) {
    switchToRegisterLink.addEventListener('click', (e) => {
      e.preventDefault();
      showRegisterScreen();
    });
  }
  if (switchToLoginLinkFromRegister) {
    switchToLoginLinkFromRegister.addEventListener('click', (e) => {
      e.preventDefault();
      showLoginScreen();
    });
  }
  if (forgotPasswordLink) {
    forgotPasswordLink.addEventListener('click', (e) => {
      e.preventDefault();
      showForgotPasswordScreen();
    });
  }
  if (backToLoginFromForgot) {
    backToLoginFromForgot.addEventListener('click', (e) => {
      e.preventDefault();
      showLoginScreen();
    });
  }
  if (backToLoginFromReset) {
    backToLoginFromReset.addEventListener('click', (e) => {
      e.preventDefault();
      showLoginScreen();
    });
  }
  if (backToLoginFromVerifyLink) {
    backToLoginFromVerifyLink.addEventListener('click', (e) => {
      e.preventDefault();
      showLoginScreen();
    });
  }
  if (closeRegisterErrorBtn) {
    closeRegisterErrorBtn.addEventListener('click', hideRegisterError);
  }
  if (closeVerifyErrorBtn) {
    closeVerifyErrorBtn.addEventListener('click', hideVerifyError);
  }
  if (closeResetPasswordErrorBtn) {
    closeResetPasswordErrorBtn.addEventListener('click', hideResetPasswordError);
  }
  if (resendCodeLink) {
    resendCodeLink.addEventListener('click', (e) => {
      e.preventDefault();
      alert("Код отправлен повторно (симуляция).");
    });
  }
  if (subscribeBtnSidebar) {
    subscribeBtnSidebar.addEventListener('click', (e) => {
      e.preventDefault();
      showSubscriptionScreen();
    });
  }
  if (closeSubscriptionOverlayBtn) {
    closeSubscriptionOverlayBtn.addEventListener('click', (e) => {
      e.preventDefault();
      showAppLayout();
      renderAuthState();
    });
  }
  planSelectButtons.forEach(button => {
    button.addEventListener('click', (e) => {
      const planCard = e.target.closest('.plan-card');
      if (planCard) {
        const planName = planCard.dataset.planName;
        const planPrice = planCard.dataset.planPrice;
        showPurchaseConfirmationModal(planName, planPrice);
      }
    });
  });
  if (closePurchaseModalBtn) {
    closePurchaseModalBtn.addEventListener('click', hidePurchaseConfirmationModal);
  }
  if (confirmPurchaseBtn) {
    confirmPurchaseBtn.addEventListener('click', () => {
      let currentPlanName = "Неизвестный тариф";
      if (selectedPlanNameModal && selectedPlanNameModal.textContent) {
        currentPlanName = selectedPlanNameModal.textContent;
      }
      alert(`Симуляция покупки тарифа «${currentPlanName}»... Переход на страницу оплаты (не реализовано).`);
      hidePurchaseConfirmationModal();
      showAppLayout();
      renderAuthState();
    });
  }
  if (closeAuthActionModalBtn) {
    closeAuthActionModalBtn.addEventListener('click', hideAuthActionRequiredModal);
  }
  if (authActionLoginBtn) {
    authActionLoginBtn.addEventListener('click', () => {
      hideAuthActionRequiredModal();
      showLoginScreen();
    });
  }
  if (authActionRegisterBtn) {
    authActionRegisterBtn.addEventListener('click', () => {
      hideAuthActionRequiredModal();
      showRegisterScreen();
    });
  }
  if (authActionGuestBtn) {
    authActionGuestBtn.addEventListener('click', async () => {
      const result = await handleApiRequest('/api/login/guest', 'POST', null, {}, false, false);
      if (result.success && result.data.access_token) {
        guestAuthToken = result.data.access_token;
        isLoggedIn = false;
        isGuestMode = true;
        guestRequestsCount = 0;
        localStorage.setItem('guestRequests', '0');
        hideAuthActionRequiredModal();
        showAppLayout();
        renderAuthState();
        console.log("Entered guest mode with token:", guestAuthToken);
      } else {
        alert("Не удалось войти как гость: " + (result.error || "Неизвестная ошибка"));
      }
    });
  }
  if (closeAttachmentLimitModalBtn) {
    closeAttachmentLimitModalBtn.addEventListener('click', hideAttachmentLimitModal);
  }
  document.querySelectorAll('.generic-limit-modal .btn-limit-action').forEach(button => {
    button.addEventListener('click', (e) => {
      const modal = e.target.closest('.generic-limit-modal');
      const action = e.target.dataset.action;
      if (modal) {
        hideLimitModal(modal);
      }
      if (action === 'continue_work_subs' || action === 'open_access_subs' || action === 'open_access_photo_subs' || action === 'open_access_smart_subs') {
        showSubscriptionScreen();
      }
    });
  });
  if (triggerModal1Btn) triggerModal1Btn.addEventListener('click', () => showLimitModal(limitExceededModal1));
  if (triggerModal2Btn) triggerModal2Btn.addEventListener('click', () => showLimitModal(limitExceededModal2));
  if (triggerModalPhotoBtn) triggerModalPhotoBtn.addEventListener('click', () => showLimitModal(limitExceededModalPhoto));
  if (triggerModalSmartBtn) triggerModalSmartBtn.addEventListener('click', () => showLimitModal(limitExceededModalSmart));
  if (btnNewChat) {
    btnNewChat.addEventListener('click', (e) => {
      e.preventDefault();
      if (!isLoggedIn && !isGuestMode) {
        showAuthActionRequiredModal(guestRequestsCount >= GUEST_REQUEST_LIMIT);
        return;
      }
      if (isGuestMode && guestRequestsCount >= GUEST_REQUEST_LIMIT) {
        showAuthActionRequiredModal(true);
        return;
      }
      handleNewChat();
    });
  }
  if (deleteChatConfirmModal) {
    if (closeDeleteConfirmModalBtn) {
      closeDeleteConfirmModalBtn.addEventListener('click', hideDeleteChatConfirmModal);
    }
    if (cancelDeleteChatBtn) {
      cancelDeleteChatBtn.addEventListener('click', hideDeleteChatConfirmModal);
    }
    if (confirmDeleteChatBtn) {
      confirmDeleteChatBtn.addEventListener('click', async () => {
        if (chatIdToDelete !== null) {
          const result = await handleApiRequest('/api/chat/delete', 'POST', {chat_id: chatIdToDelete}, {}, false, true);
          if (result.success) {
            console.log(`Chat ${chatIdToDelete} deleted successfully.`);
            userChats = userChats.filter(chat => chat.id !== chatIdToDelete);
            if (currentChatId === chatIdToDelete) {
              currentChatId = null;
              if (messageListContainer) messageListContainer.innerHTML = '';
              if (welcomeMessage) welcomeMessage.style.display = 'block';
              if (chatArea) chatArea.classList.remove('chat-active');
              if (chatTitleHeader) chatTitleHeader.style.display = 'none';
            }
            renderChatList(userChats);
            if (currentChatId === null && userChats.length > 0) {
              const firstChatId = userChats[0].id;
              const selectResult = await handleApiRequest(`/api/chat/select`, 'POST', {chat_id: firstChatId}, {}, false, true);
              if (selectResult.success) {
                currentChatId = firstChatId;
                renderChatList(userChats);
                await loadChatMessages(currentChatId);
              }
            } else if (currentChatId !== null) {
              renderChatList(userChats);
            } else {
              if (welcomeMessage) welcomeMessage.style.display = 'block';
              if (chatArea) chatArea.classList.remove('chat-active');
              if (messageListContainer) messageListContainer.style.display = 'none';
              if (chatTitleHeader) chatTitleHeader.style.display = 'none';
            }
          } else {
            alert(`Не удалось удалить чат: ${result.error || 'Неизвестная ошибка'}`);
          }
          hideDeleteChatConfirmModal();
        }
      });
    }
  }

  codeInputs.forEach((input, index) => {
    input.addEventListener('input', (e) => {
      if (e.target.value.length === 1 && index < codeInputs.length - 1) {
        codeInputs[index + 1].focus();
      }
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === "Backspace" && e.target.value.length === 0 && index > 0) {
        codeInputs[index - 1].focus();
      }
    });
  });

  const gsiScript = document.querySelector('script[src="https://accounts.google.com/gsi/client"]');
  if (gsiScript) {
    const checkGoogleReady = setInterval(() => {
      if (typeof google !== 'undefined' && google.accounts && google.accounts.id) {
        clearInterval(checkGoogleReady);
        initializeGoogleSignIn();
      }
    }, 100);
  } else {
    console.error("Google Identity Services script not found in HTML.");
  }
  if (authToken) {
    isLoggedIn = true;
    isGuestMode = false;
    console.log("User already logged in with token.");
  }
  showAppLayout();
  renderAuthState();
  updateSidebarUI(sidebar ? sidebar.classList.contains('closed') : true);
  window.addEventListener('resize', () => updateSidebarUI(sidebar ? sidebar.classList.contains('closed') : true));
});

function handleNewChat() {
  let isGuestMode = false;
  const localGuestRequests = localStorage.getItem('guestRequests');
  if (!localStorage.getItem('authToken') && localGuestRequests !== null) {
    isGuestMode = true;
  }

  currentChatId = null;
  if (messageListContainer) messageListContainer.innerHTML = '';
  if (welcomeMessage) welcomeMessage.style.display = 'block';
  if (chatArea) chatArea.classList.remove('chat-active');
  if (messageListContainer) messageListContainer.style.display = 'none';
  if (chatTitleHeader) {
    chatTitleHeader.textContent = isGuestMode ? "Гостевой чат" : "Новый чат";
    chatTitleHeader.style.display = 'block';
  }
  if (!isGuestMode) {
    renderChatList(userChats);
  } else {
    if (chatListUl) chatListUl.innerHTML = '<li style="padding: 8px 5px; color: #888;">Гостевой режим</li>';
  }
  if (chatTextArea) chatTextArea.focus();
}
