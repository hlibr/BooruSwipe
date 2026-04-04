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

        this.currentImage = null;
        this.stats = { likes: 0, dislikes: 0 };

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
        const likeX2Btn = document.getElementById('like-x2-btn');
        const dislikeX2Btn = document.getElementById('dislike-x2-btn');
        
        likeBtn.addEventListener('click', () => this.handleSwipe(true, 1));
        dislikeBtn.addEventListener('click', () => this.handleSwipe(false, 1));
        likeX2Btn.addEventListener('click', () => this.handleSwipe(true, 2));
        dislikeX2Btn.addEventListener('click', () => this.handleSwipe(false, 2));
        
        this.card.addEventListener('mousedown', this.handleStart.bind(this));
        this.card.addEventListener('touchstart', this.handleStart.bind(this), { passive: false });
        
        document.addEventListener('mousemove', this.handleMove.bind(this));
        document.addEventListener('touchmove', this.handleMove.bind(this), { passive: false });
        
        document.addEventListener('mouseup', this.handleEnd.bind(this));
        document.addEventListener('touchend', this.handleEnd.bind(this), { passive: false });
        document.addEventListener('touchcancel', this.handleEnd.bind(this));
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
            } else {
                this.currentImage = data;
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
        } finally {
            this.showLoading(false);
        }
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
