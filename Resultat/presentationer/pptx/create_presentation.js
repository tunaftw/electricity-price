const pptxgen = require('pptxgenjs');

async function createPresentation() {
    const pptx = new pptxgen();

    pptx.layout = 'LAYOUT_16x9';
    pptx.title = 'Baseload PPA Analysis';
    pptx.subject = 'Solar + Wind + Battery Energy Storage';
    pptx.author = 'Energy Analysis';

    // Color palette
    const colors = {
        primary: '1B4F72',
        secondary: '27AE60',
        accent: 'F39C12',
        dark: '2C3E50',
        light: 'F8F9FA',
        white: 'FFFFFF',
        warning: 'E74C3C'
    };

    // ========================================
    // SLIDE 1: Title
    // ========================================
    let slide = pptx.addSlide();
    slide.background = { color: colors.primary };

    slide.addText('Baseload PPA Analysis', {
        x: 0.5, y: 1.5, w: 9, h: 1,
        fontSize: 44, fontFace: 'Arial', bold: true, color: colors.white,
        align: 'center'
    });

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 4, y: 2.6, w: 2, h: 0.08,
        fill: { color: colors.secondary }
    });

    slide.addText('Solar + Wind + Battery Energy Storage', {
        x: 0.5, y: 2.9, w: 9, h: 0.6,
        fontSize: 24, fontFace: 'Arial', color: 'E8F4F8',
        align: 'center'
    });

    slide.addText('SE3 Sweden | 2024 Analysis | 1 MW Solar + 1 MW Wind', {
        x: 0.5, y: 4.5, w: 9, h: 0.4,
        fontSize: 14, fontFace: 'Arial', color: 'B8D4E3',
        align: 'center'
    });

    // ========================================
    // SLIDE 2: Executive Summary
    // ========================================
    slide = pptx.addSlide();
    slide.background = { color: colors.white };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.primary }
    });

    slide.addText('Executive Summary', {
        x: 0.5, y: 0.2, w: 9, h: 0.5,
        fontSize: 28, fontFace: 'Arial', bold: true, color: colors.white
    });

    slide.addText('Key Findings', {
        x: 0.5, y: 1.1, w: 9, h: 0.4,
        fontSize: 18, fontFace: 'Arial', bold: true, color: colors.primary
    });

    const findings = [
        { text: '100% baseload is impractical', detail: ' - requires 109 MWh battery (seasonal storage)' },
        { text: '80% baseload is the sweet spot', detail: ' - only 8 MWh battery needed' },
        { text: 'Summer nights are critical', detail: ' - not winter as commonly assumed' }
    ];

    let yPos = 1.6;
    findings.forEach(f => {
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: 0.5, y: yPos, w: 9, h: 0.5,
            fill: { color: colors.light },
            line: { color: colors.secondary, pt: 0, width: 0 }
        });
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: 0.5, y: yPos, w: 0.08, h: 0.5,
            fill: { color: colors.secondary }
        });
        slide.addText([
            { text: f.text, options: { bold: true, color: colors.primary } },
            { text: f.detail, options: { color: colors.dark } }
        ], {
            x: 0.7, y: yPos + 0.1, w: 8.7, h: 0.3,
            fontSize: 14, fontFace: 'Arial'
        });
        yPos += 0.6;
    });

    // Stats boxes
    const stats = [
        { value: '20.8%', label: 'Combined Capacity Factor' },
        { value: '8 MWh', label: 'Battery for 80% Baseload' },
        { value: '13x', label: 'More Battery for 100% vs 80%' }
    ];

    let xPos = 0.5;
    stats.forEach(s => {
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: xPos, y: 3.8, w: 2.8, h: 1.2,
            fill: { color: 'E8F6F3' },
            line: { color: colors.secondary, pt: 1 }
        });
        slide.addText(s.value, {
            x: xPos, y: 3.95, w: 2.8, h: 0.5,
            fontSize: 28, fontFace: 'Arial', bold: true, color: colors.secondary,
            align: 'center'
        });
        slide.addText(s.label, {
            x: xPos, y: 4.5, w: 2.8, h: 0.4,
            fontSize: 10, fontFace: 'Arial', color: '5D6D7E',
            align: 'center'
        });
        xPos += 3.1;
    });

    // ========================================
    // SLIDE 3: The Challenge
    // ========================================
    slide = pptx.addSlide();
    slide.background = { color: colors.white };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.primary }
    });

    slide.addText('The Challenge: Baseload PPA', {
        x: 0.5, y: 0.2, w: 9, h: 0.5,
        fontSize: 28, fontFace: 'Arial', bold: true, color: colors.white
    });

    slide.addText('What is Baseload PPA?', {
        x: 0.5, y: 1.1, w: 4.5, h: 0.4,
        fontSize: 16, fontFace: 'Arial', bold: true, color: colors.primary
    });

    slide.addText('A Power Purchase Agreement that guarantees constant power delivery 24/7/365, regardless of weather conditions.\n\nUnlike pay-as-produced contracts, the seller bears all volume risk.', {
        x: 0.5, y: 1.5, w: 4.5, h: 1.2,
        fontSize: 12, fontFace: 'Arial', color: colors.dark,
        valign: 'top'
    });

    // Challenge box
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0.5, y: 2.8, w: 4.5, h: 1.6,
        fill: { color: 'FEF5E7' },
        line: { color: colors.accent, pt: 1 }
    });

    slide.addText('The Problem', {
        x: 0.7, y: 2.9, w: 4, h: 0.35,
        fontSize: 13, fontFace: 'Arial', bold: true, color: 'D68910'
    });

    slide.addText([
        { text: '• Solar only produces during daytime\n' },
        { text: '• Wind varies unpredictably\n' },
        { text: '• Combined output still fluctuates\n' },
        { text: '• Gaps must be filled somehow' }
    ], {
        x: 0.7, y: 3.25, w: 4, h: 1.1,
        fontSize: 11, fontFace: 'Arial', color: colors.dark
    });

    // Right column
    slide.addText('Analysis Question', {
        x: 5.2, y: 1.1, w: 4.5, h: 0.4,
        fontSize: 16, fontFace: 'Arial', bold: true, color: colors.primary
    });

    slide.addText('How large a battery is needed to guarantee baseload delivery from solar + wind?', {
        x: 5.2, y: 1.5, w: 4.3, h: 0.8,
        fontSize: 13, fontFace: 'Arial', bold: true, color: colors.dark
    });

    // Solution box
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 5.2, y: 2.4, w: 4.3, h: 2,
        fill: { color: 'E8F6F3' },
        line: { color: colors.secondary, pt: 1 }
    });

    slide.addText('Our Approach', {
        x: 5.4, y: 2.5, w: 4, h: 0.35,
        fontSize: 13, fontFace: 'Arial', bold: true, color: '1E8449'
    });

    slide.addText([
        { text: '• 1 MW solar (PVsyst profile)\n' },
        { text: '• 1 MW wind (ENTSO-E actual data)\n' },
        { text: '• Hourly simulation for full year\n' },
        { text: '• Calculate max cumulative deficit\n' },
        { text: '• Test different baseload levels' }
    ], {
        x: 5.4, y: 2.9, w: 4, h: 1.4,
        fontSize: 11, fontFace: 'Arial', color: colors.dark
    });

    // ========================================
    // SLIDE 4: Methodology
    // ========================================
    slide = pptx.addSlide();
    slide.background = { color: colors.white };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.primary }
    });

    slide.addText('Methodology', {
        x: 0.5, y: 0.2, w: 9, h: 0.5,
        fontSize: 28, fontFace: 'Arial', bold: true, color: colors.white
    });

    slide.addText('Data Sources', {
        x: 0.5, y: 1.05, w: 9, h: 0.35,
        fontSize: 16, fontFace: 'Arial', bold: true, color: colors.primary
    });

    // Data source boxes
    const sources = [
        { title: 'Solar Profile', desc: 'PVsyst simulation\nsouth_lundby.csv\nCF: 11.5%' },
        { title: 'Wind Profile', desc: 'ENTSO-E actual\nSE3 2024 normalized\nCF: 30.0%' },
        { title: 'Time Period', desc: 'Full year 2024\n8,784 hours\nHourly resolution' }
    ];

    xPos = 0.5;
    sources.forEach(s => {
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: xPos, y: 1.45, w: 2.9, h: 1.1,
            fill: { color: colors.light },
            line: { color: colors.primary, pt: 0, dashType: 'solid' }
        });
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: xPos, y: 1.45, w: 2.9, h: 0.06,
            fill: { color: colors.primary }
        });
        slide.addText(s.title, {
            x: xPos + 0.1, y: 1.55, w: 2.7, h: 0.3,
            fontSize: 12, fontFace: 'Arial', bold: true, color: colors.primary
        });
        slide.addText(s.desc, {
            x: xPos + 0.1, y: 1.85, w: 2.7, h: 0.65,
            fontSize: 10, fontFace: 'Arial', color: '5D6D7E'
        });
        xPos += 3.1;
    });

    slide.addText('Battery Sizing Algorithm', {
        x: 0.5, y: 2.7, w: 9, h: 0.35,
        fontSize: 16, fontFace: 'Arial', bold: true, color: colors.primary
    });

    // Formula box
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0.5, y: 3.1, w: 9, h: 1.1,
        fill: { color: colors.dark }
    });

    slide.addText('Max Drawdown Method:', {
        x: 0.7, y: 3.2, w: 8.6, h: 0.25,
        fontSize: 11, fontFace: 'Arial', bold: true, color: colors.secondary
    });

    slide.addText('deficit[t] = max(0, baseload - production[t])\ncumsum[t] = cumsum[t-1] + (production[t] - baseload)\nbattery_size = max(peak_cumsum - cumsum[t]) for all t', {
        x: 0.7, y: 3.5, w: 8.6, h: 0.65,
        fontSize: 11, fontFace: 'Courier New', color: 'E8F4F8'
    });

    // Parameters
    const params = [
        { label: 'Solar Installed', value: '1.0 MW' },
        { label: 'Wind Installed', value: '1.0 MW' },
        { label: 'Mean Production', value: '0.415 MW' },
        { label: 'Annual Output', value: '3,647 MWh' }
    ];

    xPos = 0.5;
    params.forEach(p => {
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: xPos, y: 4.4, w: 2.2, h: 0.7,
            fill: { color: 'E8F6F3' }
        });
        slide.addText(p.label, {
            x: xPos, y: 4.45, w: 2.2, h: 0.25,
            fontSize: 9, fontFace: 'Arial', color: '5D6D7E', align: 'center'
        });
        slide.addText(p.value, {
            x: xPos, y: 4.7, w: 2.2, h: 0.35,
            fontSize: 14, fontFace: 'Arial', bold: true, color: colors.primary, align: 'center'
        });
        xPos += 2.4;
    });

    // ========================================
    // SLIDE 5: Results Table
    // ========================================
    slide = pptx.addSlide();
    slide.background = { color: colors.white };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.primary }
    });

    slide.addText('Results: Battery Sizing vs Baseload Level', {
        x: 0.5, y: 0.2, w: 9, h: 0.5,
        fontSize: 28, fontFace: 'Arial', bold: true, color: colors.white
    });

    slide.addText('Non-Linear Scaling of Battery Requirements', {
        x: 0.5, y: 1.05, w: 9, h: 0.35,
        fontSize: 16, fontFace: 'Arial', bold: true, color: colors.primary
    });

    // Table
    const tableData = [
        [{ text: 'Baseload %', options: { bold: true, fill: { color: colors.primary }, color: colors.white } },
         { text: 'Baseload (MW)', options: { bold: true, fill: { color: colors.primary }, color: colors.white } },
         { text: 'Deficit Hours', options: { bold: true, fill: { color: colors.primary }, color: colors.white } },
         { text: 'Deficit %', options: { bold: true, fill: { color: colors.primary }, color: colors.white } },
         { text: 'Battery (MWh)', options: { bold: true, fill: { color: colors.primary }, color: colors.white } },
         { text: 'Duration', options: { bold: true, fill: { color: colors.primary }, color: colors.white } }],
        ['50%', '0.208', '447', '5%', '1', '14 hours'],
        ['60%', '0.249', '1,153', '13%', '3', '22 hours'],
        [{ text: '80%', options: { bold: true, fill: { color: 'E8F6F3' } } },
         { text: '0.332', options: { bold: true, fill: { color: 'E8F6F3' } } },
         { text: '3,319', options: { bold: true, fill: { color: 'E8F6F3' } } },
         { text: '38%', options: { bold: true, fill: { color: 'E8F6F3' } } },
         { text: '8', options: { bold: true, fill: { color: 'E8F6F3' } } },
         { text: '1.6 days', options: { bold: true, fill: { color: 'E8F6F3' } } }],
        ['90%', '0.374', '4,560', '52%', '17', '2.8 days'],
        [{ text: '100%', options: { fill: { color: 'FDEDEC' } } },
         { text: '0.415', options: { fill: { color: 'FDEDEC' } } },
         { text: '5,671', options: { fill: { color: 'FDEDEC' } } },
         { text: '65%', options: { fill: { color: 'FDEDEC' } } },
         { text: '109', options: { fill: { color: 'FDEDEC' } } },
         { text: '15.5 days', options: { fill: { color: 'FDEDEC' } } }]
    ];

    slide.addTable(tableData, {
        x: 0.5, y: 1.5, w: 9, h: 2.5,
        fontSize: 12, fontFace: 'Arial',
        border: { pt: 0.5, color: 'CCCCCC' },
        align: 'center', valign: 'middle'
    });

    // Insight box
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0.5, y: 4.2, w: 9, h: 0.6,
        fill: { color: 'FEF9E7' },
        line: { color: colors.accent, pt: 0, width: 0 }
    });
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0.5, y: 4.2, w: 0.08, h: 0.6,
        fill: { color: colors.accent }
    });

    slide.addText([
        { text: 'Key Insight: ', options: { bold: true } },
        { text: 'Going from 80% to 100% baseload increases battery need by 13x (8 → 109 MWh)' }
    ], {
        x: 0.7, y: 4.35, w: 8.6, h: 0.3,
        fontSize: 13, fontFace: 'Arial', color: '7D6608'
    });

    // ========================================
    // SLIDE 6: Summer Nights
    // ========================================
    slide = pptx.addSlide();
    slide.background = { color: colors.white };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.primary }
    });

    slide.addText('Key Insight: Summer Nights Are the Bottleneck', {
        x: 0.5, y: 0.2, w: 9, h: 0.5,
        fontSize: 28, fontFace: 'Arial', bold: true, color: colors.white
    });

    // Surprise box
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0.5, y: 1.1, w: 5, h: 0.9,
        fill: { color: 'FDEDEC' },
        line: { color: colors.warning, pt: 2 }
    });

    slide.addText('Counter-Intuitive Finding', {
        x: 0.7, y: 1.2, w: 4.6, h: 0.3,
        fontSize: 13, fontFace: 'Arial', bold: true, color: 'C0392B'
    });

    slide.addText('The most challenging periods are summer nights (July-August), NOT winter darkness!', {
        x: 0.7, y: 1.5, w: 4.6, h: 0.4,
        fontSize: 11, fontFace: 'Arial', color: colors.dark
    });

    slide.addText('Why Summer Nights?', {
        x: 0.5, y: 2.15, w: 5, h: 0.3,
        fontSize: 14, fontFace: 'Arial', bold: true, color: colors.primary
    });

    slide.addText([
        { text: '• Weaker summer winds - reduced pressure gradients\n' },
        { text: '• Anticyclones persist - high pressure for days\n' },
        { text: '• Solar = zero at night - regardless of season\n' },
        { text: '• Dunkelflaute - extended low wind + no sun' }
    ], {
        x: 0.5, y: 2.5, w: 5, h: 1.2,
        fontSize: 11, fontFace: 'Arial', color: colors.dark
    });

    slide.addText('Critical Periods', {
        x: 0.5, y: 3.8, w: 5, h: 0.3,
        fontSize: 14, fontFace: 'Arial', bold: true, color: colors.primary
    });

    slide.addText([
        { text: '• 50% baseload: July 23-24 (16 hours)\n' },
        { text: '• 80% baseload: Nov 6-9 (69 hours)\n' },
        { text: '• 100% baseload: Multiple weeks' }
    ], {
        x: 0.5, y: 4.1, w: 5, h: 0.9,
        fontSize: 11, fontFace: 'Arial', color: colors.dark
    });

    // Right side - bar chart
    slide.addText('Pass Hours by Month (10% worst)', {
        x: 5.7, y: 1.1, w: 4, h: 0.3,
        fontSize: 14, fontFace: 'Arial', bold: true, color: colors.primary
    });

    const monthData = [
        { month: 'July', pct: 27 },
        { month: 'August', pct: 20 },
        { month: 'June', pct: 17 },
        { month: 'September', pct: 12 },
        { month: 'May', pct: 10 },
        { month: 'October', pct: 8 },
        { month: 'January', pct: 1 }
    ];

    yPos = 1.5;
    monthData.forEach(m => {
        slide.addText(m.month, {
            x: 5.7, y: yPos, w: 1.2, h: 0.35,
            fontSize: 10, fontFace: 'Arial', color: colors.dark
        });
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: 6.9, y: yPos + 0.05, w: 2.5, h: 0.25,
            fill: { color: 'E5E8E8' }
        });
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: 6.9, y: yPos + 0.05, w: 2.5 * (m.pct / 30), h: 0.25,
            fill: { color: m.pct > 15 ? colors.warning : colors.secondary }
        });
        slide.addText(m.pct + '%', {
            x: 6.9 + 2.5 * (m.pct / 30) + 0.1, y: yPos, w: 0.5, h: 0.35,
            fontSize: 9, fontFace: 'Arial', bold: true, color: colors.dark
        });
        yPos += 0.42;
    });

    // ========================================
    // SLIDE 7: Pass Hours Effect
    // ========================================
    slide = pptx.addSlide();
    slide.background = { color: colors.white };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.primary }
    });

    slide.addText('Key Insight: 10% Pass Reduces Battery 50-100%', {
        x: 0.5, y: 0.2, w: 9, h: 0.5,
        fontSize: 28, fontFace: 'Arial', bold: true, color: colors.white
    });

    slide.addText('Effect of Allowing Non-Delivery Hours', {
        x: 0.5, y: 1.05, w: 9, h: 0.35,
        fontSize: 16, fontFace: 'Arial', bold: true, color: colors.primary
    });

    slide.addText('If the PPA allows 10% non-delivery (878 hours/year), battery requirements drop dramatically:', {
        x: 0.5, y: 1.45, w: 9, h: 0.35,
        fontSize: 12, fontFace: 'Arial', color: colors.dark
    });

    const passTableData = [
        [{ text: 'Baseload Level', options: { bold: true, fill: { color: colors.primary }, color: colors.white } },
         { text: '100% Delivery', options: { bold: true, fill: { color: colors.primary }, color: colors.white } },
         { text: '90% Delivery', options: { bold: true, fill: { color: colors.primary }, color: colors.white } },
         { text: 'Battery Reduction', options: { bold: true, fill: { color: colors.primary }, color: colors.white } }],
        ['50% (0.208 MW)', '1.2 MWh', '0 MWh', { text: '-100%', options: { color: colors.secondary, bold: true } }],
        ['80% (0.332 MW)', '8.2 MWh', '3.3 MWh', { text: '-60%', options: { color: colors.secondary, bold: true } }],
        ['100% (0.415 MW)', '109 MWh', '57 MWh', { text: '-48%', options: { color: colors.secondary, bold: true } }]
    ];

    slide.addTable(passTableData, {
        x: 0.5, y: 1.9, w: 9, h: 1.6,
        fontSize: 12, fontFace: 'Arial',
        border: { pt: 0.5, color: 'CCCCCC' },
        align: 'center', valign: 'middle'
    });

    // Two insight boxes
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0.5, y: 3.7, w: 4.3, h: 1,
        fill: { color: 'E8F6F3' },
        line: { color: colors.secondary, pt: 0, width: 0 }
    });
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0.5, y: 3.7, w: 0.08, h: 1,
        fill: { color: colors.secondary }
    });

    slide.addText([
        { text: 'Implication: ', options: { bold: true } },
        { text: 'The worst 10% of hours drive most of the battery requirement. Small contractual flexibility yields outsized savings.' }
    ], {
        x: 0.7, y: 3.85, w: 4, h: 0.7,
        fontSize: 11, fontFace: 'Arial', color: '1E8449'
    });

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 5.2, y: 3.7, w: 4.3, h: 1,
        fill: { color: 'E8F6F3' },
        line: { color: colors.secondary, pt: 0, width: 0 }
    });
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 5.2, y: 3.7, w: 0.08, h: 1,
        fill: { color: colors.secondary }
    });

    slide.addText([
        { text: 'Recommendation: ', options: { bold: true } },
        { text: 'Negotiate for pass hours in PPA contracts - even small allowances save significant capital.' }
    ], {
        x: 5.4, y: 3.85, w: 4, h: 0.7,
        fontSize: 11, fontFace: 'Arial', color: '1E8449'
    });

    // ========================================
    // SLIDE 8: Recommendations
    // ========================================
    slide = pptx.addSlide();
    slide.background = { color: colors.white };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.primary }
    });

    slide.addText('Recommendations', {
        x: 0.5, y: 0.2, w: 9, h: 0.5,
        fontSize: 28, fontFace: 'Arial', bold: true, color: colors.white
    });

    slide.addText('Key Takeaways', {
        x: 0.5, y: 1.05, w: 9, h: 0.35,
        fontSize: 16, fontFace: 'Arial', bold: true, color: colors.primary
    });

    const recs = [
        { title: 'Target 80% Baseload', desc: 'Best balance between delivery guarantee and capital cost. 8 MWh battery vs 109 MWh for 100%.' },
        { title: 'Negotiate Pass Hours', desc: '10% pass allowance reduces battery by 50-100%. Focus on summer night flexibility.' },
        { title: '1:1 Solar/Wind Ratio', desc: 'Optimal complementarity for SE3. Solar covers days, wind covers nights/winter.' }
    ];

    xPos = 0.5;
    recs.forEach(r => {
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: xPos, y: 1.45, w: 2.9, h: 1.4,
            fill: { color: colors.light },
            line: { color: colors.secondary, pt: 0, dashType: 'solid' }
        });
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: xPos, y: 1.45, w: 2.9, h: 0.08,
            fill: { color: colors.secondary }
        });
        slide.addText(r.title, {
            x: xPos + 0.15, y: 1.6, w: 2.6, h: 0.35,
            fontSize: 12, fontFace: 'Arial', bold: true, color: colors.primary
        });
        slide.addText(r.desc, {
            x: xPos + 0.15, y: 1.95, w: 2.6, h: 0.8,
            fontSize: 10, fontFace: 'Arial', color: colors.dark
        });
        xPos += 3.1;
    });

    slide.addText('Recommended PPA Structure', {
        x: 0.5, y: 3.05, w: 9, h: 0.35,
        fontSize: 16, fontFace: 'Arial', bold: true, color: colors.primary
    });

    const structureTable = [
        [{ text: 'PPA Type', options: { bold: true, fill: { color: colors.primary }, color: colors.white } },
         { text: 'Battery Need', options: { bold: true, fill: { color: colors.primary }, color: colors.white } },
         { text: 'Risk Allocation', options: { bold: true, fill: { color: colors.primary }, color: colors.white } },
         { text: 'Premium', options: { bold: true, fill: { color: colors.primary }, color: colors.white } }],
        ['Pay-as-produced', '0 MWh', 'Buyer takes volume risk', { text: 'Low', options: { color: colors.secondary } }],
        [{ text: '80% baseload + 10% pass', options: { bold: true, fill: { color: 'E8F6F3' } } },
         { text: '~3 MWh', options: { bold: true, fill: { color: 'E8F6F3' } } },
         { text: 'Balanced risk', options: { bold: true, fill: { color: 'E8F6F3' } } },
         { text: 'Medium', options: { bold: true, fill: { color: 'E8F6F3' }, color: colors.accent } }],
        ['100% baseload', '109 MWh', 'Seller takes all risk', { text: 'Very High', options: { color: colors.warning } }]
    ];

    slide.addTable(structureTable, {
        x: 0.5, y: 3.45, w: 9, h: 1.5,
        fontSize: 11, fontFace: 'Arial',
        border: { pt: 0.5, color: 'CCCCCC' },
        align: 'center', valign: 'middle'
    });

    // ========================================
    // SLIDE 9: Appendix
    // ========================================
    slide = pptx.addSlide();
    slide.background = { color: colors.white };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.primary }
    });

    slide.addText('Appendix: Data Sources and Parameters', {
        x: 0.5, y: 0.2, w: 9, h: 0.5,
        fontSize: 28, fontFace: 'Arial', bold: true, color: colors.white
    });

    // Left column - Data Sources
    slide.addText('Data Sources', {
        x: 0.5, y: 1.05, w: 4.5, h: 0.35,
        fontSize: 14, fontFace: 'Arial', bold: true, color: colors.primary
    });

    const dataSources = [
        { title: 'Solar Production Profile', desc: 'PVsyst simulation - south_lundby.csv\nSouth-facing fixed tilt, SE3 irradiance' },
        { title: 'Wind Production Profile', desc: 'ENTSO-E Transparency Platform\nSE3 actual generation 2024, normalized' },
        { title: 'Electricity Prices', desc: 'elprisetjustnu.se API\nSE3 hourly spot prices' },
        { title: 'Analysis Period', desc: 'Full year 2024 (leap year)\n8,784 hours, hourly resolution' }
    ];

    yPos = 1.45;
    dataSources.forEach(s => {
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: 0.5, y: yPos, w: 4.5, h: 0.7,
            fill: { color: colors.light }
        });
        slide.addText(s.title, {
            x: 0.65, y: yPos + 0.05, w: 4.2, h: 0.25,
            fontSize: 11, fontFace: 'Arial', bold: true, color: colors.primary
        });
        slide.addText(s.desc, {
            x: 0.65, y: yPos + 0.3, w: 4.2, h: 0.35,
            fontSize: 9, fontFace: 'Arial', color: '5D6D7E'
        });
        yPos += 0.78;
    });

    // Right column - Parameters
    slide.addText('Key Parameters', {
        x: 5.3, y: 1.05, w: 4.2, h: 0.35,
        fontSize: 14, fontFace: 'Arial', bold: true, color: colors.primary
    });

    const paramTable = [
        ['Solar Installed', '1.0 MW'],
        ['Wind Installed', '1.0 MW'],
        ['Solar Capacity Factor', '11.5%'],
        ['Wind Capacity Factor', '30.0%'],
        ['Combined Capacity Factor', '20.8%'],
        ['Mean Production', '0.415 MW'],
        ['Annual Production', '3,647 MWh'],
        ['BESS Round-trip Efficiency', '90%']
    ];

    slide.addTable(paramTable, {
        x: 5.3, y: 1.45, w: 4.2, h: 2.1,
        fontSize: 10, fontFace: 'Arial',
        border: { pt: 0.5, color: 'E5E8E8' },
        colW: [2.5, 1.7]
    });

    // Files box
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 5.3, y: 3.7, w: 4.2, h: 1.1,
        fill: { color: colors.dark }
    });

    slide.addText('Analysis Files', {
        x: 5.45, y: 3.8, w: 3.9, h: 0.25,
        fontSize: 11, fontFace: 'Arial', bold: true, color: colors.secondary
    });

    slide.addText('elpris/baseload_analysis.py\ndata/reports/baseload_ppa_analysis.xlsx\ndata/reports/insights/baseload_ppa_key_insights.md', {
        x: 5.45, y: 4.1, w: 3.9, h: 0.65,
        fontSize: 9, fontFace: 'Courier New', color: 'E8F4F8'
    });

    // ========================================
    // Save
    // ========================================
    const outputPath = '/Users/pontusskog/Documents/Developer/electricity-price/data/reports/baseload_ppa_presentation.pptx';
    await pptx.writeFile(outputPath);
    console.log('Presentation saved to:', outputPath);
}

createPresentation().catch(console.error);
