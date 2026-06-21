# Métricas da Doroteia (consultas prontas)

> Cole qualquer bloco no **SQL Editor** do Supabase e clique **Run**.
> Nenhuma consulta expõe dado pessoal — são números agregados.

---

## 1. Demanda: o que as pessoas mais procuram (e onde)

```sql
select servico, bairro, count(*) as pedidos
from searches
group by servico, bairro
order by pedidos desc;
```

## 2. Taxa de resposta (🟢🟡🔴) — a saúde da rede

```sql
select resultado, count(*) as total,
       round(100.0 * count(*) / sum(count(*)) over (), 1) as porcentagem
from searches
group by resultado;
```

## 3. O mercado de leads: buscas que ficaram SEM resposta (🔴)

```sql
select servico, bairro, count(*) as procuras_sem_resposta
from searches
where resultado = 'vermelho'
group by servico, bairro
order by procuras_sem_resposta desc;
```
> Cada linha aqui é uma oportunidade de lead pago: gente pedindo algo que ninguém indicou.

## 4. Crescimento: novos membros por dia

```sql
select date_trunc('day', created_at)::date as dia, count(*) as novos_membros
from members
group by dia
order by dia;
```

## 5. Os convites estão funcionando?

```sql
select
  count(*) filter (where invited_by is not null) as entraram_por_convite,
  count(*) filter (where invited_by is null)     as entraram_sozinhos,
  count(*)                                        as total_membros
from members;
```

## 6. Engajamento: quanta gente indicou e quantas indicações existem

```sql
select
  (select count(*) from recommendations)                       as total_indicacoes,
  (select count(distinct member_id) from recommendations)      as membros_que_indicaram,
  (select count(*) from members where consent = true)          as membros_ativos;
```

---

### Como ler isso para o negócio
- **Pedem?** → tabelas 1 e 2 (volume de buscas).
- **Indicam?** → tabela 6.
- **Convidam?** → tabela 5.
- **Tem mercado pra cobrar?** → tabela 3 (o tamanho do 🔴).
