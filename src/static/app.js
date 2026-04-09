class SwipeCard {
    constructor() {
        this.card = document.getElementById('card');
        this.image = document.getElementById('card-image');
        this.video = document.getElementById('card-video');
        this.cardLoading = document.getElementById('card-loading');
        this.overlay = document.getElementById('overlay');
        this.likeIndicator = document.getElementById('like-indicator');
        this.dislikeIndicator = document.getElementById('dislike-indicator');
        this.loading = document.getElementById('loading');
        this.likesCount = document.getElementById('likes-count');
        this.dislikesCount = document.getElementById('dislikes-count');
        this.postLink = document.getElementById('post-link');
        this.currentTagsField = document.getElementById('current-tags');

        this.currentImage = null;
        this.stats = { likes: 0, dislikes: 0 };
        this.multiplierMenus = [];
        this.activeMultiplierMenu = null;
        this.hoverCapableQuery = window.matchMedia('(hover: hover) and (pointer: fine)');
        this.lastTouchInteractionAt = 0;
        this.touchMenuOpenDelayMs = 200;
        this.touchLongPressCancelMs = 1000;
        this.touchDragOpenDistance = 12;

        this.isDragging = false;
        this.startX = 0;
        this.startY = 0;
        this.currentX = 0;
        this.currentY = 0;
        this.threshold = Math.min(window.innerWidth * 0.15, 100);

        this.init();
    }
    
    async init() {
        this.attachEventListeners();
        await this.loadStats();
        await this.loadImage();
    }
    
    attachEventListeners() {
        const likeBtn = document.getElementById('like-btn');
        const dislikeBtn = document.getElementById('dislike-btn');
        
        likeBtn.addEventListener('click', () => this.handleSwipe(true, 1));
        dislikeBtn.addEventListener('click', () => this.handleSwipe(false, 1));
        [likeBtn, dislikeBtn].forEach((button) => this.attachButtonBlurHandlers(button));
        this.initMultiplierMenus();
        
        this.card.addEventListener('mousedown', this.handleStart.bind(this));
        this.card.addEventListener('touchstart', this.handleStart.bind(this), { passive: false });
        
        document.addEventListener('mousemove', this.handleMove.bind(this));
        document.addEventListener('touchmove', this.handleMove.bind(this), { passive: false });
        
        document.addEventListener('mouseup', this.handleEnd.bind(this));
        document.addEventListener('touchend', this.handleEnd.bind(this), { passive: false });
        document.addEventListener('touchcancel', this.handleEnd.bind(this));
    }

    initMultiplierMenus() {
        this.multiplierMenus = Array.from(document.querySelectorAll('.control-menu')).map((container) => {
            const trigger = container.querySelector('.menu-trigger');
            const options = Array.from(container.querySelectorAll('.menu-option'));
            const menu = {
                container,
                trigger,
                options,
                liked: container.dataset.liked === 'true',
                pointerId: null,
                isOpen: false,
                suppressClick: false,
                activeWeight: null,
                openTimer: null,
                longPressTimer: null,
                ignoreNextClick: false,
                openedDuringPointer: false,
                leftTriggerDuringPointer: false,
                longPressCanceled: false,
                pointerReleased: false,
                startPointerX: 0,
                startPointerY: 0,
                lastPointerX: 0,
                lastPointerY: 0,
            };

            trigger.addEventListener('pointerdown', (event) => this.handleMultiplierPointerDown(menu, event));
            trigger.addEventListener('pointerup', (event) => this.handleMultiplierPointerUp(event));
            trigger.addEventListener('pointercancel', (event) => this.handleMultiplierPointerCancel(event));
            trigger.addEventListener('click', (event) => this.handleMultiplierTriggerClick(menu, event));
            trigger.addEventListener('mouseenter', () => {
                if (this.hoverCapableQuery.matches && Date.now() - this.lastTouchInteractionAt > 800) {
                    this.openMultiplierMenu(menu);
                }
            });

            container.addEventListener('mouseleave', () => {
                if (!menu.pointerId) {
                    this.closeMultiplierMenu(menu);
                }
            });

            options.forEach((option) => {
                this.attachButtonBlurHandlers(option);
                option.addEventListener('click', (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    this.selectMultiplierOption(menu, Number(option.dataset.weight));
                });
            });

            return menu;
        });

        document.addEventListener('pointermove', (event) => this.handleMultiplierPointerMove(event));
        document.addEventListener('pointerup', (event) => this.handleMultiplierPointerUp(event));
        document.addEventListener('pointercancel', (event) => this.handleMultiplierPointerCancel(event));
        document.addEventListener('pointerdown', (event) => this.handleGlobalPointerDown(event));
    }

    handleMultiplierPointerDown(menu, event) {
        if (event.pointerType === 'mouse' && event.button !== 0) {
            return;
        }

        if (event.pointerType !== 'mouse') {
            this.lastTouchInteractionAt = Date.now();
        }

        this.closeOtherMultiplierMenus(menu);
        menu.pointerId = event.pointerId;
        menu.suppressClick = event.pointerType !== 'mouse';
        menu.ignoreNextClick = event.pointerType !== 'mouse';
        menu.activeWeight = null;
        menu.openedDuringPointer = false;
        menu.leftTriggerDuringPointer = false;
        menu.longPressCanceled = false;
        menu.pointerReleased = false;
        menu.startPointerX = event.clientX;
        menu.startPointerY = event.clientY;
        menu.lastPointerX = event.clientX;
        menu.lastPointerY = event.clientY;
        this.activeMultiplierMenu = menu;

        if (event.pointerType !== 'mouse' && menu.trigger.setPointerCapture) {
            menu.trigger.setPointerCapture(event.pointerId);
        }

        if (event.pointerType !== 'mouse') {
            event.preventDefault();
            menu.trigger.classList.add('pressed');
            this.scheduleTouchMenuOpen(menu);
            this.scheduleLongPressCancel(menu);
        }
    }

    handleMultiplierTriggerClick(menu, event) {
        if (menu.ignoreNextClick || Date.now() - this.lastTouchInteractionAt < 500) {
            event.preventDefault();
            event.stopPropagation();
            menu.ignoreNextClick = false;
            menu.suppressClick = false;
            menu.trigger.blur();
            return;
        }

        if (menu.suppressClick) {
            event.preventDefault();
            event.stopPropagation();
            menu.suppressClick = false;
            menu.trigger.blur();
            return;
        }

        this.closeMultiplierMenu(menu);
        this.handleSwipe(menu.liked, 2);
        menu.trigger.blur();
    }

    handleMultiplierPointerMove(event) {
        const menu = this.activeMultiplierMenu;
        if (!menu || menu.pointerId !== event.pointerId) {
            return;
        }

        menu.lastPointerX = event.clientX;
        menu.lastPointerY = event.clientY;

        if (!this.isPointInsideElement(menu.trigger, event.clientX, event.clientY)) {
            menu.leftTriggerDuringPointer = true;
        }

        if (!menu.isOpen && this.shouldOpenTouchMenu(menu)) {
            this.openTouchMenu(menu);
        }

        if (!menu.isOpen) {
            return;
        }

        this.updateMultiplierSelection(menu, event.clientX, event.clientY);
    }

    handleMultiplierPointerUp(event) {
        const menu = this.activeMultiplierMenu;
        if (!menu || menu.pointerId !== event.pointerId) {
            return;
        }

        menu.pointerReleased = true;
        this.clearTouchMenuOpen(menu);

        if (menu.isOpen) {
            const hoveredWeight = this.getMultiplierWeightAtPoint(event.clientX, event.clientY);
            if (hoveredWeight) {
                this.selectMultiplierOption(menu, hoveredWeight);
            } else if (this.isPointInsideElement(menu.trigger, event.clientX, event.clientY)) {
                this.closeMultiplierMenu(menu);
                if ((!menu.openedDuringPointer || !menu.leftTriggerDuringPointer) && !menu.longPressCanceled) {
                    this.handleSwipe(menu.liked, 2);
                }
                menu.trigger.blur();
            } else {
                this.closeMultiplierMenu(menu);
                menu.trigger.blur();
            }
        } else if (this.isPointInsideElement(menu.trigger, event.clientX, event.clientY) && !menu.longPressCanceled) {
            this.handleSwipe(menu.liked, 2);
            menu.trigger.blur();
        }

        this.clearLongPressCancel(menu);
        this.releasePressedState(menu.trigger);
        if (menu.trigger.hasPointerCapture && menu.trigger.hasPointerCapture(event.pointerId)) {
            menu.trigger.releasePointerCapture(event.pointerId);
        }
        menu.pointerId = null;
        this.activeMultiplierMenu = null;
    }

    handleMultiplierPointerCancel(event) {
        const menu = this.activeMultiplierMenu;
        if (!menu || menu.pointerId !== event.pointerId) {
            return;
        }

        menu.pointerReleased = true;
        this.clearTouchMenuOpen(menu);
        this.clearLongPressCancel(menu);
        this.closeMultiplierMenu(menu);
        this.releasePressedState(menu.trigger);
        menu.trigger.blur();
        if (menu.trigger.hasPointerCapture && menu.trigger.hasPointerCapture(event.pointerId)) {
            menu.trigger.releasePointerCapture(event.pointerId);
        }
        menu.pointerId = null;
        this.activeMultiplierMenu = null;
    }

    handleGlobalPointerDown(event) {
        const clickedInsideMenu = event.target.closest('.control-menu');
        if (clickedInsideMenu) {
            return;
        }

        this.closeAllMultiplierMenus();
    }

    updateMultiplierSelection(menu, clientX, clientY) {
        const activeWeight = this.getMultiplierWeightAtPoint(clientX, clientY);
        if (menu.activeWeight === activeWeight) {
            return;
        }

        menu.activeWeight = activeWeight;
        this.syncMultiplierHighlight(menu);
    }

    getMultiplierWeightAtPoint(clientX, clientY) {
        const target = document.elementFromPoint(clientX, clientY);
        const option = target ? target.closest('.menu-option') : null;
        return option ? Number(option.dataset.weight) : null;
    }

    selectMultiplierOption(menu, weight) {
        menu.suppressClick = true;
        this.closeMultiplierMenu(menu);
        menu.pointerId = null;
        this.activeMultiplierMenu = null;
        this.handleSwipe(menu.liked, weight);
    }

    openMultiplierMenu(menu) {
        this.closeOtherMultiplierMenus(menu);
        menu.isOpen = true;
        menu.container.classList.add('open');
    }

    closeMultiplierMenu(menu) {
        this.clearTouchMenuOpen(menu);
        menu.isOpen = false;
        menu.container.classList.remove('open');
        menu.activeWeight = null;
        this.syncMultiplierHighlight(menu);
    }

    closeOtherMultiplierMenus(activeMenu) {
        this.multiplierMenus.forEach((menu) => {
            if (menu !== activeMenu) {
                this.closeMultiplierMenu(menu);
                menu.pointerId = null;
            }
        });
    }

    closeAllMultiplierMenus() {
        this.multiplierMenus.forEach((menu) => {
            this.closeMultiplierMenu(menu);
            menu.pointerId = null;
        });
        this.activeMultiplierMenu = null;
    }

    syncMultiplierHighlight(menu) {
        menu.options.forEach((option) => {
            const isActive = Number(option.dataset.weight) === menu.activeWeight;
            option.classList.toggle('active', isActive);
            option.classList.toggle('pressed', isActive);
        });
    }

    attachButtonBlurHandlers(button) {
        button.addEventListener('pointerup', () => {
            window.setTimeout(() => button.blur(), 0);
        });
        button.addEventListener('pointercancel', () => {
            this.releasePressedState(button, 0);
            window.setTimeout(() => button.blur(), 0);
        });
        button.addEventListener('click', () => {
            this.releasePressedState(button);
            window.setTimeout(() => button.blur(), 0);
        });
        button.addEventListener('pointerdown', (event) => {
            if (event.pointerType !== 'mouse') {
                button.classList.add('pressed');
            }
        });
        button.addEventListener('pointerup', () => {
            this.releasePressedState(button);
        });
    }

    releasePressedState(button, delay = 90) {
        window.setTimeout(() => {
            button.classList.remove('pressed');
        }, delay);
    }

    scheduleTouchMenuOpen(menu) {
        this.clearTouchMenuOpen(menu);
        menu.openTimer = window.setTimeout(() => {
            this.openTouchMenu(menu);
        }, this.touchMenuOpenDelayMs);
    }

    openTouchMenu(menu) {
        if (menu.pointerId === null || menu.pointerReleased || this.activeMultiplierMenu !== menu) {
            return;
        }

        if (menu.isOpen) {
            return;
        }

        menu.suppressClick = true;
        menu.openedDuringPointer = true;
        this.openMultiplierMenu(menu);
        this.updateMultiplierSelection(menu, menu.lastPointerX, menu.lastPointerY);
    }

    clearTouchMenuOpen(menu) {
        if (menu.openTimer) {
            window.clearTimeout(menu.openTimer);
            menu.openTimer = null;
        }
    }

    scheduleLongPressCancel(menu) {
        this.clearLongPressCancel(menu);
        menu.longPressTimer = window.setTimeout(() => {
            menu.longPressCanceled = true;
        }, this.touchLongPressCancelMs);
    }

    clearLongPressCancel(menu) {
        if (menu.longPressTimer) {
            window.clearTimeout(menu.longPressTimer);
            menu.longPressTimer = null;
        }
    }

    shouldOpenTouchMenu(menu) {
        const deltaX = menu.lastPointerX - menu.startPointerX;
        const deltaY = menu.lastPointerY - menu.startPointerY;
        return menu.leftTriggerDuringPointer && Math.hypot(deltaX, deltaY) > this.touchDragOpenDistance;
    }

    isPointInsideElement(element, clientX, clientY) {
        const rect = element.getBoundingClientRect();
        return (
            clientX >= rect.left &&
            clientX <= rect.right &&
            clientY >= rect.top &&
            clientY <= rect.bottom
        );
    }
    
    handleStart(e) {
        if (e.type === 'touchstart') {
            e.preventDefault();
            this.startX = e.touches[0].clientX;
            this.startY = e.touches[0].clientY;
        } else {
            this.startX = e.clientX;
            this.startY = e.clientY;
        }
        
        this.isDragging = true;
        this.card.classList.add('dragging');
        this.card.classList.remove('swiping');
    }
    
    handleMove(e) {
        if (!this.isDragging) return;
        
        e.preventDefault();
        
        let clientX, clientY;
        if (e.type === 'touchmove') {
            clientX = e.touches[0].clientX;
            clientY = e.touches[0].clientY;
        } else {
            clientX = e.clientX;
            clientY = e.clientY;
        }
        
        this.currentX = clientX - this.startX;
        this.currentY = clientY - this.startY;
        
        const rotation = this.currentX * 0.1;
        this.card.style.transform = `translate(${this.currentX}px, ${this.currentY}px) rotate(${rotation}deg)`;
        
        const opacity = Math.min(Math.abs(this.currentX) / this.threshold, 1);
        
        if (this.currentX > 0) {
            this.overlay.className = 'overlay like';
            this.overlay.style.opacity = opacity;
            this.likeIndicator.style.opacity = opacity;
            this.dislikeIndicator.style.opacity = 0;
        } else {
            this.overlay.className = 'overlay dislike';
            this.overlay.style.opacity = opacity;
            this.dislikeIndicator.style.opacity = opacity;
            this.likeIndicator.style.opacity = 0;
        }
    }
    
    async handleEnd() {
        if (!this.isDragging) return;
        
        this.isDragging = false;
        this.card.classList.remove('dragging');
        
        if (Math.abs(this.currentX) > this.threshold) {
            const liked = this.currentX > 0;
            await this.completeSwipe(liked);
        } else {
            this.resetCard();
        }
        
        this.currentX = 0;
        this.currentY = 0;
    }
    
    async completeSwipe(liked) {
        this.card.classList.add('swiping');
        
        const cardWidth = this.card.offsetWidth;
        const endX = liked ? cardWidth * 2.5 : -cardWidth * 2.5;
        const rotation = liked ? 30 : -30;
        
        this.card.style.transform = `translate(${endX}px, ${this.currentY}px) rotate(${rotation}deg)`;
        this.overlay.style.opacity = 1;
        
        if (this.currentImage && this.currentImage.id) {
            await this.sendSwipe(liked, 1);
        }
        
        setTimeout(async () => {
            await this.loadImage();
        }, 200);
    }
    
    resetCard() {
        this.card.classList.add('swiping');
        this.card.style.transform = 'translate(0, 0) rotate(0)';
        this.overlay.style.opacity = 0;
        this.likeIndicator.style.opacity = 0;
        this.dislikeIndicator.style.opacity = 0;
        
        setTimeout(() => {
            this.card.classList.remove('swiping');
        }, 200);
    }
    
    async loadImage() {
        this.showLoading(true);
        this.card.style.display = 'none';
        this.card.style.transform = 'translate(0, 0) rotate(0)';
        this.card.classList.remove('swiping');
        this.overlay.style.opacity = 0;
        this.likeIndicator.style.opacity = 0;
        this.dislikeIndicator.style.opacity = 0;
        this.image.style.display = 'none';
        this.image.src = '';
        this.video.pause();
        this.video.style.display = 'none';
        this.video.removeAttribute('src');
        this.video.load();

        try {
            const response = await fetch('/api/image');
            const data = await response.json();

            if (data.error) {
                console.error('Error loading image:', data.error);
                this.image.src = '';
                this.currentImage = null;
                this.postLink.style.display = 'none';
                this.setCurrentTags([]);
            } else {
                this.currentImage = data;
                this.setCurrentTags(data.search_tags || []);
                // Update post link
                if (data.post_url) {
                    this.postLink.href = data.post_url;
                    this.updatePostLinkLabel(data.post_url);
                    this.postLink.style.display = 'inline';
                } else {
                    this.postLink.style.display = 'none';
                }

                this.card.style.display = 'block';
                this.showLoading(false);
                this.showMediaLoading(true);
                await this.displayMedia(data);
            }
        } catch (error) {
            console.error('Failed to load image:', error);
            this.currentImage = null;
            this.postLink.style.display = 'none';
            this.setCurrentTags([]);
        } finally {
            this.showLoading(false);
        }
    }

    setCurrentTags(tags) {
        this.currentTagsField.value = tags.length ? tags.join(' ') : 'No active recommendation';
        this.currentTagsField.style.height = 'auto';
        this.currentTagsField.style.height = `${this.currentTagsField.scrollHeight}px`;
    }

    async displayMedia(data) {
        const mediaType = data.media_type || this.guessMediaType(data.url);

        if (mediaType.startsWith('video/')) {
            await this.loadVideo(data.url);
            return;
        }

        await this.loadImageElement(data.url);
    }

    loadImageElement(url) {
        return new Promise((resolve) => {
            this.image.onload = () => {
                this.image.onload = null;
                this.image.onerror = null;
                this.image.style.display = 'block';
                this.showMediaLoading(false);
                resolve();
            };
            this.image.onerror = (error) => {
                console.error('Failed to load image asset:', error);
                this.image.onload = null;
                this.image.onerror = null;
                this.showMediaLoading(false);
                resolve();
            };
            this.image.src = url;
        });
    }

    loadVideo(url) {
        return new Promise((resolve) => {
            const finish = () => {
                this.video.oncanplay = null;
                this.video.onerror = null;
                this.video.style.display = 'block';
                this.showMediaLoading(false);
                this.video.play().catch((error) => {
                    console.warn('Video autoplay failed:', error);
                });
                resolve();
            };

            this.video.oncanplay = finish;
            this.video.onerror = (error) => {
                console.error('Failed to load video asset:', error);
                this.video.oncanplay = null;
                this.video.onerror = null;
                this.showMediaLoading(false);
                resolve();
            };

            this.video.src = url;
            this.video.load();
        });
    }

    guessMediaType(url) {
        const lowerUrl = (url || '').toLowerCase();
        if (lowerUrl.endsWith('.mp4')) {
            return 'video/mp4';
        }
        if (lowerUrl.endsWith('.webm')) {
            return 'video/webm';
        }
        return 'image';
    }

    updatePostLinkLabel(postUrl) {
        const lowerUrl = (postUrl || '').toLowerCase();
        if (lowerUrl.includes('gelbooru.com')) {
            this.postLink.textContent = 'View on Gelbooru';
            return;
        }
        if (lowerUrl.includes('danbooru.donmai.us')) {
            this.postLink.textContent = 'View on Danbooru';
            return;
        }
        this.postLink.textContent = 'View Post';
    }
    
    async sendSwipe(liked, weight = 1) {
        if (!this.currentImage || !this.currentImage.id) {
            return;
        }
        
        try {
            await fetch('/api/swipe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    image_id: this.currentImage.id,
                    direction: liked ? 'right' : 'left',
                    weight: weight,
                }),
            });
            
            this.stats[liked ? 'likes' : 'dislikes'] += weight;
            this.updateStatsDisplay();
        } catch (error) {
            console.error('Failed to record swipe:', error);
        }
    }
    
    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();
            
            if (!data.error) {
                this.stats.likes = data.likes || 0;
                this.stats.dislikes = data.dislikes || 0;
                this.updateStatsDisplay();
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }
    
    updateStatsDisplay() {
        this.likesCount.textContent = this.stats.likes;
        this.dislikesCount.textContent = this.stats.dislikes;
    }
    
    showLoading(show) {
        if (show) {
            this.loading.classList.add('visible');
        } else {
            this.loading.classList.remove('visible');
        }
    }

    showMediaLoading(show) {
        if (show) {
            this.cardLoading.classList.add('visible');
        } else {
            this.cardLoading.classList.remove('visible');
        }
    }
    
    async handleSwipe(liked, weight = 1) {
        if (!this.currentImage || !this.currentImage.id) {
            return;
        }
        
        this.card.classList.add('swiping');
        
        const cardWidth = this.card.offsetWidth;
        const endX = liked ? cardWidth * 2.5 : -cardWidth * 2.5;
        this.card.style.transform = `translate(${endX}px, 0) rotate(${liked ? 30 : -30}deg)`;
        
        this.overlay.className = liked ? 'overlay like' : 'overlay dislike';
        this.overlay.style.opacity = 1;
        
        await this.sendSwipe(liked, weight);
        
        setTimeout(async () => {
            await this.loadImage();
        }, 200);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new SwipeCard();
    new SettingsManager();
});

class SettingsManager {
    constructor() {
        this.settingsBtn = document.getElementById('settings-btn');
        this.settingsModal = document.getElementById('settings-modal');
        this.settingsClose = document.getElementById('settings-close');
        this.settingsForm = document.getElementById('settings-form');
        this.testBtn = document.getElementById('test-btn');
        this.testResult = document.getElementById('test-result');
        
        this.apiKeyInput = document.getElementById('api-key');
        this.baseUrlInput = document.getElementById('base-url');
        this.modelInput = document.getElementById('model');
        
        this.init();
    }
    
    async init() {
        this.settingsBtn.addEventListener('click', () => this.openModal());
        this.settingsClose.addEventListener('click', () => this.closeModal());
        this.settingsModal.addEventListener('click', (e) => {
            if (e.target === this.settingsModal) {
                this.closeModal();
            }
        });
        
        this.testBtn.addEventListener('click', () => this.testConnection());
        this.settingsForm.addEventListener('submit', (e) => this.saveSettings(e));
        
        await this.loadSettings();
    }
    
    openModal() {
        this.settingsModal.classList.add('active');
    }
    
    closeModal() {
        this.settingsModal.classList.remove('active');
        this.testResult.className = 'test-result';
        this.testResult.style.display = 'none';
    }
    
    async loadSettings() {
        try {
            const response = await fetch('/api/settings');
            const data = await response.json();
            
            if (data.api_key) {
                this.apiKeyInput.value = data.api_key;
            }
            if (data.base_url) {
                this.baseUrlInput.value = data.base_url;
            }
            if (data.model) {
                this.modelInput.value = data.model;
            }
        } catch (error) {
            console.error('Failed to load settings:', error);
        }
    }
    
    async saveSettings(e) {
        e.preventDefault();
        
        const settings = {
            api_key: this.apiKeyInput.value,
            base_url: this.baseUrlInput.value,
            model: this.modelInput.value,
        };
        
        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(settings),
            });
            
            const data = await response.json();
            
            if (data.success) {
                alert('Settings saved successfully!');
                this.closeModal();
            } else {
                alert('Failed to save settings: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            alert('Failed to save settings: ' + error.message);
        }
    }
    
    async testConnection() {
        const settings = {
            api_key: this.apiKeyInput.value,
            base_url: this.baseUrlInput.value,
            model: this.modelInput.value,
            prompt: 'Say hello',
        };
        
        this.testResult.className = 'test-result';
        this.testResult.style.display = 'block';
        this.testResult.textContent = 'Testing connection...';
        this.testBtn.disabled = true;
        
        try {
            const response = await fetch('/api/settings/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(settings),
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.testResult.className = 'test-result success';
                this.testResult.textContent = '✓ ' + data.message + (data.response ? ': "' + data.response + '"' : '');
            } else {
                this.testResult.className = 'test-result error';
                this.testResult.textContent = '✗ ' + (data.error || 'Connection failed');
            }
        } catch (error) {
            this.testResult.className = 'test-result error';
            this.testResult.textContent = '✗ Connection failed: ' + error.message;
        } finally {
            this.testBtn.disabled = false;
        }
    }
}
