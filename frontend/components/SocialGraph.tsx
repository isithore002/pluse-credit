'use client';

import { useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';
import { Transaction } from '@/lib/store';

interface SocialGraphProps {
  transactions: Transaction[];
}

type NodeDatum = {
  id: string;
  count: number;
  role: 'self' | 'contact';
};

type LinkDatum = {
  source: string;
  target: string;
  weight: number;
};

export default function SocialGraph({ transactions }: SocialGraphProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  const { nodes, links } = useMemo(() => {
    const counts = new Map<string, number>();

    for (const txn of transactions) {
      const key = (txn.vpa || 'unknown@upi').toLowerCase();
      counts.set(key, (counts.get(key) || 0) + 1);
    }

    const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 20);

    const graphNodes: NodeDatum[] = [{ id: 'you', count: transactions.length, role: 'self' }];
    const graphLinks: LinkDatum[] = [];

    for (const [vpa, count] of sorted) {
      graphNodes.push({ id: vpa, count, role: 'contact' });
      graphLinks.push({ source: 'you', target: vpa, weight: count });
    }

    return { nodes: graphNodes, links: graphLinks };
  }, [transactions]);

  useEffect(() => {
    if (!svgRef.current) return;

    const width = 980;
    const height = 420;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const simulation = d3
      .forceSimulation(nodes as any[])
      .force(
        'link',
        d3
          .forceLink(links as any[])
          .id((d: any) => d.id)
          .distance((d: any) => 80 + Math.max(0, 120 - d.weight * 6))
      )
      .force('charge', d3.forceManyBody().strength(-220))
      .force('center', d3.forceCenter(width / 2, height / 2));

    const link = svg
      .append('g')
      .attr('stroke', '#64748b')
      .attr('stroke-opacity', 0.6)
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke-width', (d: any) => Math.max(1.5, Math.min(6, d.weight / 2)));

    const node = svg
      .append('g')
      .selectAll('circle')
      .data(nodes)
      .enter()
      .append('circle')
      .attr('r', (d: any) => (d.role === 'self' ? 18 : Math.max(6, Math.min(16, 5 + d.count / 2))))
      .attr('fill', (d: any) => (d.role === 'self' ? '#a855f7' : '#06b6d4'))
      .attr('stroke', '#0f172a')
      .attr('stroke-width', 1.5);

    const label = svg
      .append('g')
      .selectAll('text')
      .data(nodes)
      .enter()
      .append('text')
      .text((d: any) => (d.id === 'you' ? 'You' : d.id.split('@')[0]))
      .attr('font-size', 11)
      .attr('fill', '#cbd5e1')
      .attr('text-anchor', 'middle')
      .attr('dy', 24);

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node.attr('cx', (d: any) => d.x).attr('cy', (d: any) => d.y);
      label.attr('x', (d: any) => d.x).attr('y', (d: any) => d.y);
    });

    return () => {
      simulation.stop();
    };
  }, [nodes, links]);

  if (!transactions.length) {
    return (
      <div className="rounded-lg border border-slate-700/70 bg-slate-900/30 p-4 text-slate-300">
        Social graph appears after loading transactions from upload or persona.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-700/70 bg-slate-900/20 p-3">
      <svg ref={svgRef} className="h-[420px] w-full" />
    </div>
  );
}
