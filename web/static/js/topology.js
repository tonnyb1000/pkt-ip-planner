/**
 * Interactive Network Topology Visualizer using Vanilla SVG
 */

document.addEventListener('DOMContentLoaded', () => {
    const svg = document.getElementById('topologySvg');
    if (!svg || !devicesData || devicesData.length === 0) return;

    const width = 800;
    const height = 450;
    const padding = 60;

    // Normalize coordinates from Packet Tracer canvas
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    devicesData.forEach(d => {
        if (d.x < minX) minX = d.x;
        if (d.x > maxX) maxX = d.x;
        if (d.y < minY) minY = d.y;
        if (d.y > maxY) maxY = d.y;
    });

    const spanX = (maxX - minX) || 100;
    const spanY = (maxY - minY) || 100;

    const posMap = {};
    devicesData.forEach((d, idx) => {
        let posX, posY;
        if (spanX > 50 && spanY > 50) {
            posX = padding + ((d.x - minX) / spanX) * (width - 2 * padding);
            posY = padding + ((d.y - minY) / spanY) * (height - 2 * padding);
        } else {
            // Fallback grid if coordinates are identical
            const cols = Math.ceil(Math.sqrt(devicesData.length));
            const row = Math.floor(idx / cols);
            const col = idx % cols;
            posX = padding + (col * (width - 2 * padding)) / (cols || 1);
            posY = padding + (row * (height - 2 * padding)) / (cols || 1);
        }
        posMap[d.name] = { x: posX, y: posY, device: d };
    });

    // Clear SVG
    svg.innerHTML = '';

    // Create SVG Defs for markers and gradients
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    defs.innerHTML = `
        <filter id="nodeShadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#000000" flood-opacity="0.12"/>
        </filter>
    `;
    svg.appendChild(defs);

    // Group for Links
    const linksGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    linksGroup.setAttribute('class', 'links-group');
    svg.appendChild(linksGroup);

    // Group for Nodes
    const nodesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    nodesGroup.setAttribute('class', 'nodes-group');
    svg.appendChild(nodesGroup);

    // Render Links
    linksData.forEach(link => {
        const p1 = posMap[link.source];
        const p2 = posMap[link.target];
        if (!p1 || !p2) return;

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', p1.x);
        line.setAttribute('y1', p1.y);
        line.setAttribute('x2', p2.x);
        line.setAttribute('y2', p2.y);
        line.setAttribute('stroke', '#64748b');
        line.setAttribute('stroke-width', '2.5');
        line.setAttribute('stroke-dasharray', link.cable === 'Serial' ? '6,4' : 'none');
        line.setAttribute('class', `topology-link link-${link.source} link-${link.target}`);

        // Tooltip
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = `${link.source} (${link.sourcePort}) <--> ${link.target} (${link.targetPort})`;
        line.appendChild(title);

        linksGroup.appendChild(line);

        // Port Labels at 25% and 75%
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;

        const lbl1 = createPortLabel(p1.x + dx * 0.22, p1.y + dy * 0.22, link.sourcePort);
        const lbl2 = createPortLabel(p1.x + dx * 0.78, p1.y + dy * 0.78, link.targetPort);
        linksGroup.appendChild(lbl1);
        linksGroup.appendChild(lbl2);
    });

    // Render Nodes
    devicesData.forEach(d => {
        const pos = posMap[d.name];
        if (!pos) return;

        const nodeG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        nodeG.setAttribute('class', `topology-node node-${d.name}`);
        nodeG.setAttribute('transform', `translate(${pos.x}, ${pos.y})`);
        nodeG.style.cursor = 'pointer';

        let shape, fill, stroke, icon;
        if (d.kind === 'Router') {
            fill = '#6366f1';
            stroke = '#4338ca';
            icon = '🔀';
            shape = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            shape.setAttribute('r', '22');
        } else if (d.kind === 'Switch' || d.kind === 'Hub') {
            fill = '#10b981';
            stroke = '#047857';
            icon = '⏹️';
            shape = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            shape.setAttribute('x', '-20');
            shape.setAttribute('y', '-20');
            shape.setAttribute('width', '40');
            shape.setAttribute('height', '40');
            shape.setAttribute('rx', '6');
        } else {
            fill = '#3b82f6';
            stroke = '#1d4ed8';
            icon = '💻';
            shape = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            shape.setAttribute('x', '-22');
            shape.setAttribute('y', '-18');
            shape.setAttribute('width', '44');
            shape.setAttribute('height', '36');
            shape.setAttribute('rx', '8');
        }

        shape.setAttribute('fill', fill);
        shape.setAttribute('stroke', stroke);
        shape.setAttribute('stroke-width', '2');
        shape.setAttribute('filter', 'url(#nodeShadow)');
        nodeG.appendChild(shape);

        // Icon inside shape
        const textIcon = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        textIcon.setAttribute('text-anchor', 'middle');
        textIcon.setAttribute('dy', '5');
        textIcon.setAttribute('font-size', '14');
        textIcon.textContent = icon;
        nodeG.appendChild(textIcon);

        // Device Name Label below
        const textLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        textLabel.setAttribute('text-anchor', 'middle');
        textLabel.setAttribute('dy', '34');
        textLabel.setAttribute('font-size', '12');
        textLabel.setAttribute('font-weight', '600');
        textLabel.setAttribute('fill', '#0f172a');
        textLabel.textContent = d.name;
        nodeG.appendChild(textLabel);

        // Hover events
        nodeG.addEventListener('mouseenter', () => {
            shape.setAttribute('stroke-width', '4');
            document.querySelectorAll(`.link-${d.name}`).forEach(l => {
                l.setAttribute('stroke', '#2563eb');
                l.setAttribute('stroke-width', '4');
            });
        });

        nodeG.addEventListener('mouseleave', () => {
            shape.setAttribute('stroke-width', '2');
            document.querySelectorAll(`.link-${d.name}`).forEach(l => {
                l.setAttribute('stroke', '#64748b');
                l.setAttribute('stroke-width', '2.5');
            });
        });

        nodesGroup.appendChild(nodeG);
    });

    function createPortLabel(x, y, text) {
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('transform', `translate(${x}, ${y})`);

        const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        bg.setAttribute('x', '-18');
        bg.setAttribute('y', '-8');
        bg.setAttribute('width', '36');
        bg.setAttribute('height', '16');
        bg.setAttribute('rx', '3');
        bg.setAttribute('fill', '#ffffff');
        bg.setAttribute('stroke', '#cbd5e1');
        bg.setAttribute('stroke-width', '1');
        g.appendChild(bg);

        const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        txt.setAttribute('text-anchor', 'middle');
        txt.setAttribute('dy', '3.5');
        txt.setAttribute('font-size', '9');
        txt.setAttribute('font-family', 'monospace');
        txt.setAttribute('fill', '#475569');
        txt.textContent = text.length > 5 ? text.replace('FastEthernet', 'Fa').replace('GigabitEthernet', 'Gi').replace('Serial', 'Se') : text;
        g.appendChild(txt);

        return g;
    }
});
