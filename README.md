# Agenda para Nail Designer

Aplicacao web simples para registrar agendamentos usando Python, SQLite, HTML e CSS.

## Recursos

- Cadastro de cliente, telefone, servico, data, horario e observacoes
- Horarios disponiveis calculados com base nos horarios liberados pela dona e nos agendamentos existentes
- Lista dos proximos atendimentos
- Cancelamento de agendamento direto pela interface
- Painel admin com login com senha hash
- Visao financeira com faturamento previsto
- Link direto para conversa no WhatsApp das clientes
- Cadastro e edicao de servicos e precos pela pagina de Configurações
- Mensagem personalizada no link do WhatsApp com servico, data e horario
- Duracao estimada por servico
- Horarios de funcionamento marcados pela dona na pagina de Configurações, de 06:00 ate 00:00
- Tela final com confirmacao Agendada com sucesso

## Tecnologias

- Flask
- Flask-SQLAlchemy
- SQLite
- HTML e CSS

## Como rodar

1. Ative o ambiente virtual do projeto.
2. Instale as dependencias:

```bash
pip install -r requirements.txt
```

3. Inicie a aplicacao:

```bash
python app.py
```

4. Abra no navegador:

```text
http://127.0.0.1:5000
```

O banco sera criado automaticamente no primeiro start.

## Painel admin

- URL: /admin/login
- Usuario padrao: duda
- Senha padrao: 123456

Depois do primeiro login, altere usuario e senha na pagina Mudar senha.