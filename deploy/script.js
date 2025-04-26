document.addEventListener('DOMContentLoaded', function() {
    // Get both timeline blocks and regular sections
    const sections = document.querySelectorAll('section[id], .timeline-block');
    const navLinks = document.querySelectorAll('.vertical-nav a');
    const submenuToggles = document.querySelectorAll('.has-submenu > a');
    let isScrolling = false;
    let scrollTimeout;

    // Get element's offset from the top of the page
    function getOffset(el) {
        let top = 0;
        let element = el;
        
        do {
            top += element.offsetTop;
            element = element.offsetParent;
        } while (element);

        return top;
    }

    // Get current section based on scroll position
    function getCurrentSection() {
        const scrollPosition = window.scrollY + window.innerHeight / 3;
        
        let currentSection = null;
        let minDistance = Infinity;
        let activeParentSections = new Set();

        sections.forEach(section => {
            const sectionTop = getOffset(section);
            const sectionBottom = sectionTop + section.offsetHeight;
            const distance = Math.abs(scrollPosition - (sectionTop + section.offsetHeight / 2));

            // Check if we're within this section's range
            if (scrollPosition >= sectionTop && scrollPosition <= sectionBottom) {
                if (distance < minDistance) {
                    currentSection = section;
                    minDistance = distance;
                }
                
                // If this is a subsection, add its parent section to active sections
                if (section.classList.contains('timeline-block')) {
                    const parentSection = section.closest('section[id]');
                    if (parentSection) {
                        activeParentSections.add(parentSection);
                    }
                } else if (section.id) {
                    // If it's a main section, add it to active sections
                    activeParentSections.add(section);
                }
            }
        });

        return { currentSection, activeParentSections };
    }

    // Update active section in navigation
    function updateActiveSection() {
        const { currentSection, activeParentSections } = getCurrentSection();
        
        if (!currentSection) return;

        // Remove all active classes first
        navLinks.forEach(link => link.classList.remove('active'));
        document.querySelectorAll('.has-submenu').forEach(item => item.classList.remove('active'));

        // Find and activate the corresponding link
        const currentId = currentSection.id;
        const currentLink = document.querySelector(`.vertical-nav a[href="#${currentId}"]`);
        
        if (currentLink) {
            currentLink.classList.add('active');
            
            // If it's a submenu item, activate its parent
            const parentSubmenu = currentLink.closest('.submenu');
            if (parentSubmenu) {
                const parentItem = parentSubmenu.closest('.has-submenu');
                if (parentItem) {
                    parentItem.classList.add('active');
                    parentItem.querySelector('a').classList.add('active');
                }
            }
        }

        // Activate all parent sections that are in view
        activeParentSections.forEach(parentSection => {
            const parentId = parentSection.id;
            const parentLink = document.querySelector(`.vertical-nav a[href="#${parentId}"]`);
            if (parentLink) {
                parentLink.classList.add('active');
                const parentItem = parentLink.closest('.has-submenu');
                if (parentItem) {
                    parentItem.classList.add('active');
                    parentItem.querySelector('a').classList.add('active');
                }
            }
        });
    }

    // Handle scroll events with debouncing
    window.addEventListener('scroll', () => {
        if (!isScrolling) {
            window.requestAnimationFrame(() => {
                updateActiveSection();
                isScrolling = false;
            });
        }
        isScrolling = true;

        // Clear and set new timeout
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
            updateActiveSection();
        }, 100);
    });

    // Handle navigation link clicks
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId && targetId !== '#' && !targetId.startsWith('http')) {
                e.preventDefault();
                const targetSection = document.querySelector(targetId);
                if (targetSection) {
                    const offset = getOffset(targetSection);
                    window.scrollTo({
                        top: offset - 20,
                        behavior: 'smooth'
                    });
                }
            }
        });
    });

    // Handle submenu toggles
    submenuToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            const parent = this.parentElement;
            parent.classList.toggle('active');
        });
    });

    // Initial check on page load
    updateActiveSection();

    // Update on window resize
    window.addEventListener('resize', () => {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
            updateActiveSection();
        }, 100);
    });

    // Chatbot functionality
    const chatbotContainer = document.querySelector('.chatbot-container');
    const chatbotToggle = document.querySelector('.chatbot-toggle');
    const chatInput = document.querySelector('.chat-input input');
    const sendButton = document.querySelector('.send-button');
    const chatMessages = document.querySelector('.chat-messages');

    // Toggle chatbot visibility
    chatbotToggle.addEventListener('click', function() {
        chatbotContainer.classList.toggle('collapsed');
    });

    // Handle sending messages
    async function sendMessage() {
        const message = chatInput.value.trim();
        if (message) {
            // Add user message to chat
            addMessage(message, 'user');
            chatInput.value = '';

            try {
                // Show loading indicator
                const loadingDiv = document.createElement('div');
                loadingDiv.className = 'message bot loading';
                loadingDiv.innerHTML = '<p>AI Tommy is typing...</p>';
                chatMessages.appendChild(loadingDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;

                // Call the backend API
                const response = await fetch('http://127.0.0.1:5000/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                    },
                    mode: 'cors',
                    credentials: 'omit',
                    body: JSON.stringify({ message: message })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();

                // Remove loading indicator
                if (loadingDiv.parentNode) {
                    chatMessages.removeChild(loadingDiv);
                }

                if (data.error) {
                    console.error('Server error:', data.error);
                    addMessage("Sorry, I'm having trouble connecting right now. Please try again later.", 'bot');
                } else {
                    addMessage(data.response, 'bot');
                }
            } catch (error) {
                console.error('Error:', error);
                // Remove loading indicator if it still exists
                const loadingDiv = chatMessages.querySelector('.loading');
                if (loadingDiv) {
                    chatMessages.removeChild(loadingDiv);
                }
                addMessage("Sorry, I'm having trouble connecting right now. Please try again later.", 'bot');
            }
        }
    }

    // Add message to chat
    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        messageDiv.innerHTML = `<p>${text}</p>`;
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Send message on button click
    sendButton.addEventListener('click', sendMessage);

    // Send message on Enter key
    chatInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
}); 