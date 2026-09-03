# Dicionário de campos — caso Illicit Matrix

Conhecimento de domínio sobre os campos do dataset (não é dado do caso — §51).

- **record_id**: identificador único da linha bruta. Chave candidata natural.
- **event_id**: identificador da ocorrência (transação/acesso). Unidade de evento
  para deduplicação (§20). Registros com o mesmo event_id podem ser duplicatas
  técnicas (reimportação) ou divergência real.
- **name**: nome nominal. Nome idêntico NÃO implica mesma pessoa (P4). Homônimos
  são esperados.
- **cpf**: identificador altamente discriminante. Divergência de CPF entre nomes
  iguais indica pessoas distintas (§85).
- **dob**: data de nascimento. Segundo identificador discriminante.
- **phone**: telefone; múltiplos formatos exigem normalização (PHONE_BR_E164_V2).
- **amount / currency**: valor e moeda da transação.
- **company / counterparty**: empresa vinculada e contraparte.
- **timestamp**: momento declarado; três formatos no caso. Timezone explícito não
  valida o relógio de origem (P6).
