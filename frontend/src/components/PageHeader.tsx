import { useNavigate } from 'react-router-dom';
import { Icon } from './Icon';

type Props = {
  titulo: string;
  voltarPara?: string;
};

export function PageHeader({ titulo, voltarPara }: Props) {
  const navigate = useNavigate();

  function voltar() {
    if (voltarPara) {
      navigate(voltarPara);
    } else {
      navigate(-1);
    }
  }

  return (
    <header className="page-header">
      <button type="button" className="botao-icone" onClick={voltar} aria-label="Voltar">
        <Icon name="voltar" />
      </button>
      <h1 className="page-title">{titulo}</h1>
    </header>
  );
}
