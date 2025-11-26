/**
 * Ultraviolet Proxy Clone - Client-side JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.querySelector('.search-input');
    const searchForm = document.querySelector('.search-form');
    
    // Auto-focus search input
    if (searchInput) {
        searchInput.focus();
    }
    
    // Handle form submission
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            const url = searchInput.value.trim();
            
            if (!url) {
                e.preventDefault();
                searchInput.classList.add('shake');
                setTimeout(() => searchInput.classList.remove('shake'), 500);
                return;
            }
            
            // Add loading state
            const button = searchForm.querySelector('.search-button');
            button.innerHTML = '<span class="loading">Loading...</span>';
            button.disabled = true;
        });
    }
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Focus search with Ctrl+K or /
        if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && document.activeElement !== searchInput)) {
            e.preventDefault();
            searchInput.focus();
            searchInput.select();
        }
        
        // Quick navigation with number keys when not focused on input
        if (document.activeElement !== searchInput) {
            const quickLinks = document.querySelectorAll('.quick-link');
            const num = parseInt(e.key);
            if (num >= 1 && num <= quickLinks.length) {
                quickLinks[num - 1].click();
            }
        }
    });
    
    // Add ripple effect to buttons
    document.querySelectorAll('.search-button, .quick-link, .back-button').forEach(button => {
        button.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            
            ripple.style.cssText = `
                position: absolute;
                background: rgba(255, 255, 255, 0.3);
                border-radius: 50%;
                pointer-events: none;
                width: 100px;
                height: 100px;
                left: ${e.clientX - rect.left - 50}px;
                top: ${e.clientY - rect.top - 50}px;
                transform: scale(0);
                animation: ripple 0.6s linear;
            `;
            
            this.style.position = 'relative';
            this.style.overflow = 'hidden';
            this.appendChild(ripple);
            
            setTimeout(() => ripple.remove(), 600);
        });
    });
    
    // Add ripple animation style
    const style = document.createElement('style');
    style.textContent = `
        @keyframes ripple {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
        
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            20%, 60% { transform: translateX(-5px); }
            40%, 80% { transform: translateX(5px); }
        }
        
        .shake {
            animation: shake 0.5s ease;
        }
        
        .loading {
            display: inline-block;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    `;
    document.head.appendChild(style);
    
    console.log('🌐 Ultraviolet Proxy Clone loaded');
    console.log('Keyboard shortcuts:');
    console.log('  Ctrl+K or / : Focus search');
    console.log('  1-6 : Quick link navigation');
});


/**
 * URL encoding/decoding utilities
 */
const ProxyUtils = {
    encode: function(url) {
        return btoa(url).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
    },
    
    decode: function(encoded) {
        // Add padding back
        let padded = encoded.replace(/-/g, '+').replace(/_/g, '/');
        while (padded.length % 4) {
            padded += '=';
        }
        return atob(padded);
    },
    
    buildProxyUrl: function(url, prefix = '/service/') {
        return prefix + this.encode(url);
    }
};

// Export for use in other scripts
window.ProxyUtils = ProxyUtils;
