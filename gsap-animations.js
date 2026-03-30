// gsap-animations.js — GSAP + ScrollTrigger animations for tommymoran.com

document.addEventListener('DOMContentLoaded', function () {
    if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') return;

    gsap.registerPlugin(ScrollTrigger);

    const isMobile = window.innerWidth <= 768;

    // ─── 1. PAGE LOAD ENTRANCE SEQUENCE (desktop only) ───────────────────────
    if (!isMobile) {
        // Set initial invisible states before first paint
        gsap.set('.left-side',                    { x: -60, opacity: 0 });
        gsap.set('#sidebar-logo',                 { opacity: 0, y: -12 });
        gsap.set('.vertical-nav > ul > li',       { opacity: 0, x: -18 });
        gsap.set('.profile-image',                { opacity: 0, scale: 0.88 });
        gsap.set('.hero-text h1',                 { opacity: 0, y: 35 });
        gsap.set('.titles p',                     { opacity: 0, y: 20 });
        gsap.set('.contact-info',                 { opacity: 0, y: 15 });
        gsap.set('.ecg-path', {
            strokeDasharray: 1200,
            strokeDashoffset: 1200,
            opacity: 0
        });
        gsap.set('.chat-bubble', { opacity: 0, scale: 0.5 });

        const loadTl = gsap.timeline({ defaults: { ease: 'power3.out' } });

        loadTl
            // Sidebar slides in from left
            .to('.left-side', { x: 0, opacity: 1, duration: 0.72 })
            // Logo fades down
            .to('#sidebar-logo', { opacity: 1, y: 0, duration: 0.45 }, '-=0.38')
            // Nav items stagger in
            .to('.vertical-nav > ul > li', {
                opacity: 1, x: 0,
                stagger: 0.07, duration: 0.4
            }, '-=0.28')
            // Profile photo scales up from centre
            .to('.profile-image', {
                opacity: 1, scale: 1,
                duration: 0.75, ease: 'back.out(1.4)'
            }, '-=0.55')
            // Name slides up
            .to('.hero-text h1', { opacity: 1, y: 0, duration: 0.62 }, '-=0.52')
            // Title lines stagger up
            .to('.titles p', {
                opacity: 1, y: 0,
                stagger: 0.13, duration: 0.5
            }, '-=0.38')
            // Contact info
            .to('.contact-info', { opacity: 1, y: 0, duration: 0.42 }, '-=0.22')
            // ECG line draws from left to right
            .to('.ecg-path', {
                strokeDashoffset: 0,
                opacity: 0.28,
                duration: 1.9,
                ease: 'power2.inOut'
            }, '-=1.3')
            // Chat bubble pops in
            .to('.chat-bubble', {
                opacity: 1, scale: 1,
                duration: 0.5, ease: 'back.out(2)'
            }, '-=1.1');
    }

    // ─── 2. SCROLL PROGRESS BAR ───────────────────────────────────────────────
    // Thin vertical line on the sidebar's right edge that fills as you scroll
    gsap.to('.scroll-progress', {
        scaleY: 1,
        ease: 'none',
        scrollTrigger: {
            trigger: 'body',
            start: 'top top',
            end: 'bottom bottom',
            scrub: 0.15
        }
    });

    // ─── 3. ABOUT SECTION ────────────────────────────────────────────────────
    gsap.from('.about h2', {
        scrollTrigger: { trigger: '.about', start: 'top 82%' },
        opacity: 0, y: 38, duration: 0.7, ease: 'power2.out'
    });
    gsap.from('.about-text', {
        scrollTrigger: { trigger: '.about-text', start: 'top 86%' },
        opacity: 0, y: 24, duration: 0.8, ease: 'power2.out', delay: 0.1
    });

    // ─── 4. SECTION H2 HEADINGS ──────────────────────────────────────────────
    gsap.utils
        .toArray('#timeline h2, #research h2, .memberships h2, .interests h2, .references h2')
        .forEach(h2 => {
            gsap.from(h2, {
                scrollTrigger: { trigger: h2, start: 'top 85%' },
                opacity: 0, y: 36, duration: 0.68, ease: 'power2.out'
            });
        });

    // ─── 5. TIMELINE BLOCK H3 HEADERS ────────────────────────────────────────
    gsap.utils.toArray('.timeline-block h3').forEach(h3 => {
        gsap.from(h3, {
            scrollTrigger: { trigger: h3, start: 'top 88%' },
            opacity: 0, x: -28, duration: 0.58, ease: 'power2.out'
        });
    });

    // ─── 6. TIMELINE ITEMS ───────────────────────────────────────────────────
    // Each block's items stagger in from the left
    gsap.utils.toArray('.timeline-block').forEach(block => {
        const items = block.querySelectorAll('.timeline-item');
        if (!items.length) return;
        gsap.from(items, {
            scrollTrigger: { trigger: block, start: 'top 82%' },
            opacity: 0,
            x: -28,
            stagger: 0.055,
            duration: 0.48,
            ease: 'power2.out'
        });
    });

    // ─── 7. INTEREST CARDS ───────────────────────────────────────────────────
    const interestItems = document.querySelectorAll('.interest-item');
    if (interestItems.length) {
        gsap.from(interestItems, {
            scrollTrigger: { trigger: '.interests-grid', start: 'top 80%' },
            opacity: 0,
            y: 36,
            scale: 0.93,
            stagger: 0.12,
            duration: 0.62,
            ease: 'back.out(1.3)'
        });
    }

    // ─── 8. REFERENCE CARDS ──────────────────────────────────────────────────
    const refItems = document.querySelectorAll('.reference-item');
    if (refItems.length) {
        gsap.from(refItems, {
            scrollTrigger: { trigger: '.references-grid', start: 'top 80%' },
            opacity: 0,
            y: 28,
            stagger: 0.1,
            duration: 0.52,
            ease: 'power2.out'
        });
    }

    // ─── 9. MEMBERSHIPS ──────────────────────────────────────────────────────
    const membershipItems = document.querySelectorAll('.membership-list li');
    if (membershipItems.length) {
        gsap.from(membershipItems, {
            scrollTrigger: { trigger: '.memberships', start: 'top 82%' },
            opacity: 0,
            x: -20,
            stagger: 0.1,
            duration: 0.48,
            ease: 'power2.out'
        });
    }

    // ─── 10. PROFILE IMAGE PARALLAX ──────────────────────────────────────────
    if (!isMobile) {
        gsap.to('.profile-image', {
            scrollTrigger: {
                trigger: '.hero',
                start: 'top top',
                end: 'bottom top',
                scrub: 1.5
            },
            y: -50,
            ease: 'none'
        });
    }

    // ─── 11. FOOTER ──────────────────────────────────────────────────────────
    gsap.from('footer', {
        scrollTrigger: { trigger: 'footer', start: 'top 92%' },
        opacity: 0, y: 18, duration: 0.48, ease: 'power2.out'
    });

    // ─── 12. FLOATING CHAT BUBBLE ────────────────────────────────────────────
    const chatBubble      = document.getElementById('chat-bubble');
    const chatbotPanel    = document.getElementById('chatbot-container');
    const chatCloseBtn    = document.getElementById('chatbot-close');

    if (chatBubble && chatbotPanel) {
        let chatOpen = false;

        // Gentle idle pulse on the bubble
        const bubblePulse = gsap.to(chatBubble, {
            scale: 1.1,
            duration: 1.1,
            repeat: -1,
            yoyo: true,
            ease: 'sine.inOut',
            paused: true
        });
        // Delay the pulse so it doesn't fire during the entrance animation
        setTimeout(() => bubblePulse.play(), isMobile ? 0 : 2400);

        function openChat() {
            if (chatOpen) return;
            chatOpen = true;
            bubblePulse.pause();
            gsap.to(chatBubble, {
                scale: 0, opacity: 0,
                duration: 0.22, ease: 'power2.in'
            });
            chatbotPanel.style.pointerEvents = 'auto';
            gsap.fromTo(chatbotPanel,
                { opacity: 0, scale: 0.82, y: 18 },
                { opacity: 1, scale: 1, y: 0, duration: 0.42, ease: 'back.out(1.6)', delay: 0.1 }
            );
        }

        function closeChat() {
            if (!chatOpen) return;
            chatOpen = false;
            gsap.to(chatbotPanel, {
                opacity: 0, scale: 0.84, y: 18,
                duration: 0.28, ease: 'power2.in',
                onComplete: () => { chatbotPanel.style.pointerEvents = 'none'; }
            });
            gsap.to(chatBubble, {
                scale: 1, opacity: 1,
                duration: 0.42, ease: 'back.out(1.7)', delay: 0.2,
                onComplete: () => { setTimeout(() => bubblePulse.play(), 1200); }
            });
        }

        chatBubble.addEventListener('click', openChat);
        if (chatCloseBtn) chatCloseBtn.addEventListener('click', closeChat);
    }
});
